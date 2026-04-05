from unittest.mock import patch

from odoo import fields

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_mx_cfdi.tests.common import ACTIVE_CFDI_RESPONSE, CFDITestMixin

SAMPLE_CFDI_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    TipoDeComprobante="I" FormaPago="03" MetodoPago="PUE" Serie="INV" Folio="1">
  <cfdi:Emisor Rfc="RFC123456" Nombre="Issuer"/>
  <cfdi:Receptor Rfc="XAXX010101010" Nombre="Customer" UsoCFDI="G03"/>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
        UUID="11111111-1111-1111-1111-111111111111"/>
  </cfdi:Complemento>
</cfdi:Comprobante>"""


class CFDIAccountTestCommon(CFDITestMixin, AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.write(
            {
                "country_id": cls.env.ref("base.mx").id,
                "l10n_mx_cfdi_auto": False,
            }
        )
        cls.service = cls._create_cfdi_service()
        cls.issuer = cls._create_cfdi_issuer(cls.service)
        cls.issuer.write(
            {
                "registered": True,
                "zip": "06000",
            }
        )
        cls.partner = cls.customer = cls.env["res.partner"].create(
            {
                "name": "CFDI Customer",
                "vat": "XAXX010101010",
                "zip": "06000",
                "country_id": cls.env.ref("base.mx").id,
                "tax_regime": cls.env.ref("l10n_mx_catalogs.c_regimen_fiscal_616").id,
                "cfdi_use_id": cls.env.ref("l10n_mx_catalogs.c_uso_cfdi_G03").id,
                "payment_method_id": cls.env.ref(
                    "l10n_mx_catalogs.c_metodo_pago_PUE"
                ).id,
                "payment_form_id": cls.env.ref("l10n_mx_catalogs.c_forma_pago_03").id,
            }
        )
        cls.cfdi_product = cls.env["product.product"].create(
            {
                "name": "CFDI Test Product",
                "list_price": 100.0,
                "l10n_mx_cfdi_product_code_id": cls.env.ref(
                    "l10n_mx_catalogs.c_clave_prod_serv_01010101"
                ).id,
                "l10n_mx_cfdi_product_measurement_unit_id": cls.env.ref(
                    "l10n_mx_catalogs.c_clave_unidad_H87"
                ).id,
                "taxes_id": [(6, 0, cls.tax_sale_a.ids)],
            }
        )

    def _create_cfdi_invoice(self, **extra):
        vals = {
            "move_type": "out_invoice",
            "partner_id": self.customer.id,
            "invoice_date": fields.Date.today(),
            "cfdi_required": True,
            "issuer_id": self.issuer.id,
            "receiver_id": self.customer.id,
            "cfdi_use_id": self.customer.cfdi_use_id.id,
            "payment_method_id": self.customer.payment_method_id.id,
            "payment_form_id": self.customer.payment_form_id.id,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.cfdi_product.id,
                        "quantity": 1,
                        "price_unit": 100.0,
                    },
                )
            ],
        }
        vals.update(extra)
        return self.env["account.move"].create(vals)

    def _create_published_invoice_cfdi(self, invoice):
        document = self._create_document(
            type="I",
            state="published",
            related_invoice_id=invoice.id,
            receiver_id=invoice.receiver_id.id,
        )
        invoice.related_cert_ids = [(4, document.id)]
        return document

    def _mock_cfdi_publish(self):
        return patch.object(
            type(self.service),
            "create_cfdi",
            return_value=ACTIVE_CFDI_RESPONSE,
        )

    def _post_cfdi_invoice(self, invoice):
        auto = self.company.l10n_mx_cfdi_auto
        self.company.l10n_mx_cfdi_auto = False
        invoice.action_post()
        self.company.l10n_mx_cfdi_auto = auto
        return invoice

    def _register_invoice_payment(self, invoice, payment_form=None):
        payment_form = payment_form or self.env.ref("l10n_mx_catalogs.c_forma_pago_03")
        register = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "amount": invoice.amount_residual,
                    "payment_form_id": payment_form.id,
                }
            )
        )
        return register._create_payments()

    def _iva_tax(self):
        return self.env["account.tax"].search(
            [
                ("company_id", "=", self.company.id),
                ("type_tax_use", "=", "sale"),
                ("name", "ilike", "IVA"),
            ],
            limit=1,
        ) or self.env["account.tax"].create(
            {
                "name": "IVA 16%",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": self.tax_sale_a.tax_group_id.id,
                "company_id": self.company.id,
            }
        )
