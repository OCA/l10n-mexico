# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.l10n_mx_cfdi_account.tests.common import CFDIAccountTestCommon


@tagged("post_install", "-at_install")
class TestAddendaAudi(CFDIAccountTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.addenda_view = cls.env.ref(
            "l10n_mx_cfdi_account_addenda_audi.l10n_mx_cfdi_account_addenda_audi"
        )
        cls.customer.write(
            {
                "l10n_mx_edi_addenda": cls.addenda_view.id,
                "audi_supplier_email": "supplier@audi.test",
                "audi_supplier_number": "SUP-001",
            }
        )
        cls.cfdi_product.product_tmpl_id.audi_ref = "AUDI-PART-123"

    def test_addenda_view_flag(self):
        self.assertTrue(self.addenda_view.l10n_mx_edi_addenda_flag)
        self.assertEqual(self.addenda_view.name, "Addenda Audi")

    def test_partner_addenda_related_name(self):
        self.assertEqual(self.customer.l10n_mx_edi_addenda_name, "Addenda Audi")

    def test_audi_flag_compute(self):
        invoice = self._create_cfdi_invoice()
        self.assertTrue(invoice.audi_flag)
        partner_no_addenda = self.env["res.partner"].create(
            {"name": "No Addenda", "country_id": self.env.ref("base.mx").id}
        )
        invoice.partner_id = partner_no_addenda
        self.assertFalse(invoice.audi_flag)

    def test_product_audi_ref_onchange(self):
        invoice = self._create_cfdi_invoice()
        line = invoice.invoice_line_ids[0]
        line.audi_product_ref = False
        line.product_id = self.cfdi_product
        line._onchange_product_id_audi_ref()
        self.assertEqual(line.audi_product_ref, "AUDI-PART-123")

    def test_render_audi_addenda(self):
        invoice = self._create_cfdi_invoice(
            ref="PO-42",
            audi_business_unit="BU1",
            audi_applicant_email="applicant@audi.test",
            audi_tax_code="IVA16",
            audi_fiscal_document_type="FA",
            audi_document_type="INVOICE",
        )
        invoice.invoice_line_ids[0].audi_product_ref = "AUDI-PART-123"
        rendered = invoice._l10n_mx_edi_addenda_audi_render()
        rendered = str(rendered)
        self.assertIn("AUDI-PART-123", rendered)
        self.assertIn("SUP-001", rendered)
        self.assertIn("supplier@audi.test", rendered)
        self.assertIn("PO-42", rendered)
        self.assertIn("applicant@audi.test", rendered)

    def test_attach_addenda_service_success(self):
        client = MagicMock()
        client.CfdiMultiEmisor.build_http_request.return_value = {"ok": True}
        with patch.object(type(self.service), "_get_pac", return_value=client):
            result = self.service.attach_addenda("tracking-1", "<Addenda/>")
        self.assertEqual(result, {"ok": True})
        client.CfdiMultiEmisor.build_http_request.assert_called_once_with(
            "put",
            "addenda/tracking-1/nu",
            "<Addenda/>",
        )

    def test_attach_addenda_service_error(self):
        with patch.object(
            type(self.service),
            "_get_pac",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(UserError):
                self.service.attach_addenda("tracking-1", "<Addenda/>")

    def test_create_invoice_cfdi_attaches_addenda(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        invoice.write(
            {
                "audi_business_unit": "BU1",
                "audi_applicant_email": "applicant@audi.test",
                "audi_tax_code": "IVA16",
                "audi_fiscal_document_type": "FA",
                "audi_document_type": "INVOICE",
            }
        )
        invoice.invoice_line_ids[0].audi_product_ref = "AUDI-PART-123"
        with (
            self._mock_cfdi_publish(),
            patch.object(
                type(self.service),
                "attach_addenda",
                return_value=b"xml",
            ) as mocked_attach,
        ):
            invoice.create_invoice_cfdi()
            mocked_attach.assert_called_once()
            self.assertTrue(invoice.cfdi_document_id)
            self.assertTrue(invoice.cfdi_document_id.tracking_id)

    def test_attach_skipped_without_tracking(self):
        invoice = self._create_cfdi_invoice()
        with patch.object(
            type(invoice),
            "_l10n_mx_edi_addenda_audi_render",
        ) as mocked_render:
            result = invoice._l10n_mx_edi_addenda_audi_attach()
            self.assertFalse(result)
            mocked_render.assert_not_called()

    def test_create_invoice_cfdi_without_audi_flag_no_attach(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Regular Customer",
                "vat": "XAXX010101010",
                "zip": "06000",
                "country_id": self.env.ref("base.mx").id,
                "tax_regime": self.env.ref("l10n_mx_catalogs.c_regimen_fiscal_616").id,
                "cfdi_use_id": self.env.ref("l10n_mx_catalogs.c_uso_cfdi_G03").id,
                "payment_method_id": self.env.ref(
                    "l10n_mx_catalogs.c_metodo_pago_PUE"
                ).id,
                "payment_form_id": self.env.ref("l10n_mx_catalogs.c_forma_pago_03").id,
            }
        )
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(partner_id=partner.id, receiver_id=partner.id)
        )
        self.assertFalse(invoice.audi_flag)
        with (
            self._mock_cfdi_publish(),
            patch.object(
                type(self.service),
                "attach_addenda",
                return_value=b"xml",
            ) as mocked_attach,
        ):
            invoice.create_invoice_cfdi()
            mocked_attach.assert_not_called()

    def test_attach_decodes_bytes_render(self):
        invoice = self._create_cfdi_invoice()
        document = self._create_published_invoice_cfdi(invoice)
        document.tracking_id = "track-bytes"
        with (
            patch.object(
                type(invoice),
                "_l10n_mx_edi_addenda_audi_render",
                return_value=b"<Addenda/>",
            ),
            patch.object(
                type(self.service),
                "attach_addenda",
                return_value={"ok": True},
            ) as mocked_attach,
        ):
            invoice._l10n_mx_edi_addenda_audi_attach()
            mocked_attach.assert_called_once_with("track-bytes", "<Addenda/>")

    def test_product_audi_ref_onchange_without_ref(self):
        product = self.env["product.product"].create(
            {
                "name": "No Audi Ref",
                "list_price": 10.0,
                "l10n_mx_cfdi_product_code_id": self.env.ref(
                    "l10n_mx_catalogs.c_clave_prod_serv_01010101"
                ).id,
                "l10n_mx_cfdi_product_measurement_unit_id": self.env.ref(
                    "l10n_mx_catalogs.c_clave_unidad_H87"
                ).id,
            }
        )
        invoice = self._create_cfdi_invoice()
        line = invoice.invoice_line_ids[0]
        line.audi_product_ref = "KEEP"
        line.product_id = product
        line._onchange_product_id_audi_ref()
        self.assertEqual(line.audi_product_ref, "KEEP")
