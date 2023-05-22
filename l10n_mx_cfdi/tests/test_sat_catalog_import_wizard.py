import base64
import os

import xlrd

from odoo.tests import tagged, TransactionCase


@tagged("-standard", "l10n_mx_cfdi")
class TestSatCatalogImportWizard(TransactionCase):
    """
    Test importing SAT Catalogs into Odoo using the SAT Catalog Import Wizard
    """

    url_cat_cfdi_4_0 = "http://omawww.sat.gob.mx/tramitesyservicios/Paginas/documentos/catCFDI_V_4_05052023.xls"

    def setUp(self):
        self.catalog_file_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "data",
            "tests",
            "temp",
            "catCFDI_V_4_05052023.xls",
        )

        # download catalog file if it doesn't exist
        if not os.path.exists(self.catalog_file_path):
            import urllib.request

            urllib.request.urlretrieve(self.url_cat_cfdi_4_0, self.catalog_file_path)

        with open(self.catalog_file_path, "rb") as catalog_file:
            catalog_file_data = catalog_file.read()

        self.wizard = self.env["l10n_mx_cfdi.sat_catalogs_import_wizard"].create(
            {
                "catalog_file": base64.b64encode(catalog_file_data),
                "catalog_type": "CFDI_4_0",
            }
        )

        self.book = xlrd.open_workbook(file_contents=catalog_file_data)
        self.assertTrue(self.book)

    def test_cfdi_4_0_catalog_page_mapping_to_model(self):
        """
        Test that the catalog page is mapped to the correct model
        """

        res = self.wizard._get_default_cfdi_4_0_mappings(self.book)
        self.assertDictEqual(
            res,
            {
                "c_TipoDeComprobante": "l10n_mx_cfdi.cfdi_type",
                "c_CodigoPostal_Parte_1": "l10n_mx_cfdi.cfdi_zip_codes",
                "c_CodigoPostal_Parte_2": "l10n_mx_cfdi.cfdi_zip_codes",
                "C_Municipio": "l10n_mx_cfdi.cfdi_municipality_code",
                "C_Localidad": "l10n_mx_cfdi.cfdi_locality_code",
                "c_ClaveProdServ": "l10n_mx_cfdi.cfdi_product_and_service_code",
                "c_Pais": "res.country",
                "c_Estado": "res.country.state",
            },
        )

    def test_import_c_TipoDeComprobante_sheet(self):
        """
        Test importing the c_TipoDeComprobante sheet
        """

        line = self.wizard.line_ids.create(
            {
                "wizard_id": self.wizard.id,
                "sheet_title": "c_TipoDeComprobante",
                "target_model": "l10n_mx_cfdi.cfdi_type",
            }
        )

        sheet = self._find_line_sheet(line)
        line._import_sheet(sheet)

        expected_values = ['I', 'E', 'T', 'N', 'P']
        tipo_comprobantes = self.env['l10n_mx_cfdi.cfdi_type'].search([]).mapped('code')
        self.assertListEqual(expected_values, tipo_comprobantes)

    def test_import_c_FormaPago_sheet(self):
        """
        Test importing the c_FormaPago sheet
        """

        line = self.wizard.line_ids.create(
            {
                "wizard_id": self.wizard.id,
                "sheet_title": "c_FormaPago",
                "target_model": "l10n_mx_cfdi.cfdi_payment_way",
            }
        )

        sheet = self._find_line_sheet(line)
        line._import_sheet(sheet)

        expected_codes = ['01', '02', '03', '04', '05', '06', '08', '12', '13', '14', '15', '17', '23', '24', '25',
                          '26', '27', '28', '29', '30', '31', '99']
        forma_pagos = self.env['l10n_mx_cfdi.cfdi_payment_way'].search([]).mapped('code')
        self.assertListEqual(expected_codes, forma_pagos)

    def test_import_c_MetodoPago_sheet(self):
        """
        Test importing the c_MetodoPago sheet
        """

        line = self.wizard.line_ids.create(
            {
                "wizard_id": self.wizard.id,
                "sheet_title": "c_MetodoPago",
                "target_model": "l10n_mx_cfdi.cfdi_payment_policy",
            }
        )

        sheet = self._find_line_sheet(line)
        line._import_sheet(sheet)

        expected_codes = ['PUE', 'PPD']
        metodo_pagos = self.env['l10n_mx_cfdi.cfdi_payment_policy'].search([]).mapped('code')
        self.assertListEqual(expected_codes, metodo_pagos)


    def _find_line_sheet(self, line):
        sheet = next(
            (s for s in self.book.sheets() if s.name == line.sheet_title),
            None
        )
        return sheet
