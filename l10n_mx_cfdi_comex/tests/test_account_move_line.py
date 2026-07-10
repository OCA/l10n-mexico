from .common import CFDIComexTestCommon


class TestAccountMoveLineComex(CFDIComexTestCommon):
    def test_invoice_line_pedimento_and_import_details(self):
        pedimento = self._create_pedimento()
        invoice, _lot = self._create_sale_invoice_with_lot(pedimento)
        line = invoice.invoice_line_ids.filtered(lambda ln: ln.product_id)
        self.assertIn(pedimento, line.l10n_mx_cfdi_pedimento_ids)
        self.assertTrue(line.l10n_mx_cfid_import_details_required)
        self.assertIn("Fracción:", line.l10n_mx_cfid_import_details)
        self.assertIn(pedimento.number, line.l10n_mx_cfid_import_details)
        self.assertIn("Pedimento:", line.name)

    def test_gater_cfdi_item_data_pedimento(self):
        pedimento = self._create_pedimento()
        invoice, _lot = self._create_sale_invoice_with_lot(pedimento)
        line = invoice.invoice_line_ids.filtered(lambda ln: ln.product_id)
        item = line._gater_cfdi_item_data()
        self.assertIn("NumerosPedimento", item)
        self.assertEqual(
            item["NumerosPedimento"],
            [pedimento.number.replace(" ", "  ")],
        )

    def test_import_details_not_required_without_pedimento(self):
        invoice = self._create_cfdi_invoice(
            invoice_line_ids=[
                (
                    0,
                    0,
                    {
                        "product_id": self.comex_product.id,
                        "quantity": 1,
                        "price_unit": 100.0,
                    },
                )
            ]
        )
        line = invoice.invoice_line_ids[0]
        self.assertFalse(line.l10n_mx_cfid_import_details_required)
        self.assertFalse(line.l10n_mx_cfid_import_details)

    def test_compute_pedimento_ids_without_sale_lines(self):
        invoice = self._create_cfdi_invoice()
        line = invoice.invoice_line_ids[0]
        self.assertFalse(line.l10n_mx_cfdi_pedimento_ids)

    def test_gater_cfdi_item_data_without_pedimento(self):
        invoice = self._create_cfdi_invoice()
        line = invoice.invoice_line_ids[0]
        item = line._gater_cfdi_item_data()
        self.assertNotIn("NumerosPedimento", item)

    def test_import_details_required_false_for_non_mx_company(self):
        pedimento = self._create_pedimento()
        invoice, _lot = self._create_sale_invoice_with_lot(pedimento)
        line = invoice.invoice_line_ids.filtered(lambda ln: ln.product_id)
        line.company_id.country_id = self.env.ref("base.us")
        line._compute_l10n_mx_cfid_import_details_required()
        self.assertFalse(line.l10n_mx_cfid_import_details_required)
