# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from unittest.mock import Mock, patch

import requests
from satcfdi.pacs import TaxpayerStatus

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import CFDIAccountTestCommon

ACCOUNT_MOVE_MODULE = "odoo.addons.l10n_mx_cfdi_account.models.account_move"
SAT_69B_MODULE = "odoo.addons.l10n_mx_cfdi_account.models.sat_69b"


@tagged("post_install", "-at_install")
class TestSAT69BBlacklist(CFDIAccountTestCommon):
    def setUp(self):
        super().setUp()
        self.company.l10n_mx_cfdi_sat_69b_check = True

    def test_check_is_disabled_by_default(self):
        company = self.env["res.company"].create({"name": "No 69-B check"})
        self.assertFalse(company.l10n_mx_cfdi_sat_69b_check)

    def test_check_does_nothing_when_disabled(self):
        self.company.l10n_mx_cfdi_sat_69b_check = False
        invoice = self._create_cfdi_invoice()
        invoice.receiver_id.vat = "AAA010101AAA"
        with patch.object(
            type(invoice),
            "_l10n_mx_cfdi_sat_69b_status",
            return_value=TaxpayerStatus.DEFINITIVO,
        ) as mock_status:
            invoice._l10n_mx_cfdi_check_receiver_not_on_sat_blacklist()
        mock_status.assert_not_called()

    def _mock_sat_csv(self, rows, status_code=200):
        lines = ["Legal notice", "Listado completo", "No,RFC,Nombre,Situación"]
        lines += [f'{i},{rfc},"NAME, SA",{status}' for i, (rfc, status) in rows]
        response = Mock(status_code=status_code)
        response.content = "\r\n".join(lines).encode("windows-1250")
        if status_code != 200:
            response.raise_for_status.side_effect = requests.HTTPError("boom")
        return patch(f"{SAT_69B_MODULE}.requests.get", return_value=response)

    def test_sat_69b_status_reads_stored_list(self):
        self._sat_69b_status_patcher.stop()
        invoice = self._create_cfdi_invoice()
        rows = enumerate([("AAA010101AAA", "Definitivo"), ("BBB010101BBB", "Presunto")])
        with self._mock_sat_csv(rows) as mock_get:
            # No stored copy yet: downloaded on the spot, then kept.
            self.assertEqual(
                invoice._l10n_mx_cfdi_sat_69b_status("AAA010101AAA"), "Definitivo"
            )
            self.assertEqual(
                invoice._l10n_mx_cfdi_sat_69b_status("BBB010101BBB"), "Presunto"
            )
            self.assertIsNone(invoice._l10n_mx_cfdi_sat_69b_status("CCC010101CCC"))
            mock_get.assert_called_once()
        self.assertEqual(len(self.env["l10n_mx_cfdi_account.sat_69b"]._attachment()), 1)

    def test_sat_69b_cron_replaces_stored_list(self):
        sat_69b = self.env["l10n_mx_cfdi_account.sat_69b"]
        with self._mock_sat_csv(enumerate([("AAA010101AAA", "Presunto")])):
            sat_69b._cron_refresh()
        attachment = sat_69b._attachment()
        with self._mock_sat_csv(enumerate([("AAA010101AAA", "Desvirtuado")])):
            sat_69b._cron_refresh()
        self.assertEqual(sat_69b._attachment(), attachment)
        self.assertEqual(sat_69b._status("AAA010101AAA"), "Desvirtuado")

    def test_sat_69b_cron_skips_download_when_no_company_checks(self):
        self.env["res.company"].search([]).l10n_mx_cfdi_sat_69b_check = False
        sat_69b = self.env["l10n_mx_cfdi_account.sat_69b"]
        with self._mock_sat_csv(enumerate([("AAA010101AAA", "Presunto")])) as mock_get:
            sat_69b._cron_refresh()
        mock_get.assert_not_called()
        self.assertFalse(sat_69b._attachment())

    def test_sat_69b_failed_refresh_keeps_stored_list(self):
        sat_69b = self.env["l10n_mx_cfdi_account.sat_69b"]
        with self._mock_sat_csv(enumerate([("AAA010101AAA", "Presunto")])):
            sat_69b._cron_refresh()
        with (
            self._mock_sat_csv([], status_code=503),
            self.assertLogs(SAT_69B_MODULE, level="ERROR"),
        ):
            sat_69b._cron_refresh()
        with self._mock_sat_csv([]), self.assertLogs(SAT_69B_MODULE, level="ERROR"):
            sat_69b._cron_refresh()
        self.assertEqual(sat_69b._status("AAA010101AAA"), "Presunto")

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
            self.assertLogs(ACCOUNT_MOVE_MODULE, level="ERROR") as logs,
            self.assertRaises(UserError) as err,
        ):
            invoice._l10n_mx_cfdi_check_receiver_not_on_sat_blacklist()
        self.assertIn("Could not verify SAT list 69-B", str(err.exception))
        self.assertIn("sat unavailable", "".join(logs.output))

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
