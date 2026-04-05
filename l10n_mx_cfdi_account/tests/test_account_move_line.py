from .common import CFDIAccountTestCommon


class TestAccountMoveLine(CFDIAccountTestCommon):
    def test_compute_cfdi_fields(self):
        invoice = self._create_cfdi_invoice()
        line = invoice.invoice_line_ids[0]
        self.assertEqual(line.cfdi_subtotal, 100.0)
        self.assertEqual(line.cfdi_price_unit, 100.0)
        self.assertEqual(line.cfdi_discount, 0.0)

    def test_compute_cfdi_fields_with_discount(self):
        invoice = self._create_cfdi_invoice(
            invoice_line_ids=[
                (
                    0,
                    0,
                    {
                        "product_id": self.cfdi_product.id,
                        "quantity": 1,
                        "price_unit": 100.0,
                        "discount": 10.0,
                    },
                )
            ]
        )
        line = invoice.invoice_line_ids[0]
        self.assertGreater(line.cfdi_discount, 0)

    def test_compute_cfdi_fields_with_default_code(self):
        self.cfdi_product.default_code = "SKU-001"
        invoice = self._create_cfdi_invoice()
        item = invoice.invoice_line_ids[0]._gater_cfdi_item_data()
        self.assertEqual(item["IdentificationNumber"], "SKU-001")

    def test_compute_cfdi_fields_with_retention_tax(self):
        retention_tax = self.env["account.tax"].create(
            {
                "name": "IVA RET 4%",
                "amount": 4.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": self.tax_sale_a.tax_group_id.id,
            }
        )
        product = self.env["product.product"].create(
            {
                "name": "Retention Product",
                "list_price": 100.0,
                "l10n_mx_cfdi_product_code_id": self.env.ref(
                    "l10n_mx_catalogs.c_clave_prod_serv_01010101"
                ).id,
                "l10n_mx_cfdi_product_measurement_unit_id": self.env.ref(
                    "l10n_mx_catalogs.c_clave_unidad_H87"
                ).id,
                "taxes_id": [(6, 0, retention_tax.ids)],
            }
        )
        invoice = self._create_cfdi_invoice(
            invoice_line_ids=[
                (0, 0, {"product_id": product.id, "quantity": 1, "price_unit": 100.0})
            ]
        )
        item = invoice.invoice_line_ids[0]._gater_cfdi_item_data()
        self.assertEqual(item["TaxObject"], "02")
        self.assertTrue(item["Taxes"][0]["IsRetention"])

    def test_compute_cfdi_fields_with_price_include_tax(self):
        included_tax = self.env["account.tax"].create(
            {
                "name": "IVA 16% Included",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "price_include": True,
                "tax_group_id": self.tax_sale_a.tax_group_id.id,
                "company_id": self.company.id,
            }
        )
        product = self.env["product.product"].create(
            {
                "name": "Included Tax Product",
                "list_price": 116.0,
                "l10n_mx_cfdi_product_code_id": self.env.ref(
                    "l10n_mx_catalogs.c_clave_prod_serv_01010101"
                ).id,
                "l10n_mx_cfdi_product_measurement_unit_id": self.env.ref(
                    "l10n_mx_catalogs.c_clave_unidad_H87"
                ).id,
                "taxes_id": [(6, 0, included_tax.ids)],
            }
        )
        invoice = self._create_cfdi_invoice(
            invoice_line_ids=[
                (0, 0, {"product_id": product.id, "quantity": 1, "price_unit": 116.0})
            ]
        )
        line = invoice.invoice_line_ids[0]
        item = line._gater_cfdi_item_data()
        self.assertEqual(item["TaxObject"], "02")
        self.assertGreater(line.cfdi_subtotal, 0)
