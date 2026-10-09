# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from unittest.mock import patch

from satcfdi.pacs import TaxpayerStatus

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import CFDIAccountTestCommon


@tagged("post_install", "-at_install")
class TestSAT69BBlacklist(CFDIAccountTestCommon):
    def test_sat_69b_status_uses_satcfdi(self):
        self._sat_69b_status_patcher.stop()
        invoice = self._create_cfdi_invoice()
        with patch(
            "odoo.addons.l10n_mx_cfdi_account.models.account_move.SAT"
        ) as mock_sat:
            mock_sat.return_value.list_69b.return_value = TaxpayerStatus.DESVIRTUADO
            status = invoice._l10n_mx_cfdi_sat_69b_status("AAA010101AAA")
        self.assertEqual(status, TaxpayerStatus.DESVIRTUADO)
        mock_sat.return_value.list_69b.assert_called_once_with("AAA010101AAA")

    def test_check_skips_generic_and_empty_rfc(self):
        invoice = self._create_cfdi_invoice()
        invoice.receiver_id.vat = "XAXX010101000"
        with patch.object(type(invoice), "_l10n_mx_cfdi_sat_69b_status") as mock_status:
            invoice._l10n_mx_cfdi_check_receiver_not_on_sat_blacklist()
            mock_status.assert_not_called()
        invoice.receiver_id.vat = "XEXX010101000"
        with patch.object(type(invoice), "_l10n_mx_cfdi_sat_69b_status") as mock_status:
            invoice._l10n_mx_cfdi_check_receiver_not_on_sat_blacklist()
            mock_status.assert_not_called()
        invoice.receiver_id.vat = False
        with patch.object(type(invoice), "_l10n_mx_cfdi_sat_69b_status") as mock_status:
            invoice._l10n_mx_cfdi_check_receiver_not_on_sat_blacklist()
            mock_status.assert_not_called()

    def test_check_normalizes_rfc(self):
        invoice = self._create_cfdi_invoice()
        invoice.receiver_id.vat = " aaa-010101-aaa "
        self.assertEqual(invoice._l10n_mx_cfdi_receiver_rfc(), "AAA010101AAA")

    def test_check_allows_cleared_or_unlisted_rfc(self):
        invoice = self._create_cfdi_invoice()
        invoice.receiver_id.vat = "AAA010101AAA"
        with patch.object(
            type(invoice),
            "_l10n_mx_cfdi_sat_69b_status",
            return_value=TaxpayerStatus.SENTENCIA_FAVORABLE,
        ):
            invoice._l10n_mx_cfdi_check_receiver_not_on_sat_blacklist()
        with patch.object(
            type(invoice),
            "_l10n_mx_cfdi_sat_69b_status",
            return_value=TaxpayerStatus.DESVIRTUADO,
        ):
            invoice._l10n_mx_cfdi_check_receiver_not_on_sat_blacklist()
        with patch.object(
            type(invoice),
            "_l10n_mx_cfdi_sat_69b_status",
            return_value=None,
        ):
            invoice._l10n_mx_cfdi_check_receiver_not_on_sat_blacklist()
        with patch.object(
            type(invoice),
            "_l10n_mx_cfdi_sat_69b_status",
            return_value="Otro",
        ):
            invoice._l10n_mx_cfdi_check_receiver_not_on_sat_blacklist()

    def test_check_blocks_presunto_and_definitivo(self):
        invoice = self._create_cfdi_invoice()
        invoice.receiver_id.vat = "AAA010101AAA"
        with (
            patch.object(
                type(invoice),
                "_l10n_mx_cfdi_sat_69b_status",
                return_value=TaxpayerStatus.PRESUNTO,
            ),
            self.assertRaises(UserError) as err,
        ):
            invoice._l10n_mx_cfdi_check_receiver_not_on_sat_blacklist()
        self.assertIn("69-B", str(err.exception))
        self.assertIn("Presunto", str(err.exception))
        with (
            patch.object(
                type(invoice),
                "_l10n_mx_cfdi_sat_69b_status",
                return_value=TaxpayerStatus.DEFINITIVO,
            ),
            self.assertRaises(UserError) as err,
        ):
            invoice._l10n_mx_cfdi_check_receiver_not_on_sat_blacklist()
        self.assertIn("Definitivo", str(err.exception))

    def test_check_blocks_plain_string_status(self):
        invoice = self._create_cfdi_invoice()
        invoice.receiver_id.vat = "AAA010101AAA"
        with (
            patch.object(
                type(invoice),
                "_l10n_mx_cfdi_sat_69b_status",
                return_value="Definitivo",
            ),
            self.assertRaises(UserError),
        ):
            invoice._l10n_mx_cfdi_check_receiver_not_on_sat_blacklist()

    def test_check_raises_when_list_unavailable(self):
        invoice = self._create_cfdi_invoice()
        invoice.receiver_id.vat = "AAA010101AAA"
        with (
            patch.object(
                type(invoice),
                "_l10n_mx_cfdi_sat_69b_status",
                side_effect=OSError("sat unavailable"),
            ),
            self.assertRaises(UserError) as err,
        ):
            invoice._l10n_mx_cfdi_check_receiver_not_on_sat_blacklist()
        self.assertIn("Could not verify SAT list 69-B", str(err.exception))

    def test_create_invoice_cfdi_blocks_blacklisted_customer(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        invoice.receiver_id.vat = "AAA010101AAA"
        with (
            patch.object(
                type(invoice),
                "_l10n_mx_cfdi_sat_69b_status",
                return_value=TaxpayerStatus.DEFINITIVO,
            ),
            self.assertRaises(UserError),
        ):
            invoice.create_invoice_cfdi()
        self.assertFalse(invoice.related_cert_ids)

    def test_create_refund_cfdi_blocks_blacklisted_customer(self):
        refund = self._create_cfdi_invoice(move_type="out_refund")
        refund.receiver_id.vat = "AAA010101AAA"
        with (
            patch.object(
                type(refund),
                "_l10n_mx_cfdi_sat_69b_status",
                return_value=TaxpayerStatus.PRESUNTO,
            ),
            self.assertRaises(UserError),
        ):
            refund.create_refund_cfdi()
        self.assertFalse(refund.related_cert_ids)
