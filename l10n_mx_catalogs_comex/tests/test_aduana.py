from odoo.tests.common import TransactionCase


class TestAduana(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Aduana = cls.env["l10n_mx_catalogs.c_aduana"]

    def test_display_name_compute(self):
        aduana = self.Aduana.create(
            {
                "code": "999",
                "name": "Test Customs",
                "city": "Test City",
                "state": "Test State",
            }
        )
        self.assertEqual(aduana.display_name, "999 - Test Customs")

    def test_loaded_catalog_data(self):
        aduana = self.Aduana.search([("code", "=", "010")], limit=1)
        self.assertTrue(aduana)
        self.assertIn("ACAPULCO", aduana.name.upper())
