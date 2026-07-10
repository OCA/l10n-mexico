from odoo.tests.common import TransactionCase


class TestFraccion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Fraccion = cls.env["l10n_mx_catalogs.c_fraccion"]

    def test_display_name_compute(self):
        fraccion = self.Fraccion.create(
            {
                "code": "01010101",
                "name": "Test tariff code",
            }
        )
        self.assertEqual(fraccion.display_name, "[01010101] Test tariff code")

    def test_display_name_without_code(self):
        fraccion = self.Fraccion.create({"code": "", "name": "Only description"})
        self.assertEqual(fraccion.display_name, "Only description")

    def test_name_search(self):
        results = self.Fraccion.name_search(name="0101210100")
        self.assertTrue(results)
