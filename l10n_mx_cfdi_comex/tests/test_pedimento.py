from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestPedimento(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customs = cls.env["l10n_mx_catalogs.c_aduana"].search([], limit=1)

    def _create_pedimento(self, number="15 48 3009 0001234", **extra):
        vals = {
            "number": number,
            "customs_id": self.customs.id,
            "date": "2024-01-15",
        }
        vals.update(extra)
        return self.env["l10n_mx_cfdi.pedimento"].create(vals)

    def test_compute_name(self):
        pedimento = self._create_pedimento()
        self.assertIn("15 48 3009 0001234", pedimento.name)
        self.assertIn(self.customs.city or self.customs.name, pedimento.name)

    def test_compute_name_partial_fields(self):
        pedimento = self.env["l10n_mx_cfdi.pedimento"].new(
            {
                "number": "15 48 3009 0001234",
                "date": False,
                "customs_id": False,
            }
        )
        pedimento._compute_name()
        self.assertEqual(pedimento.name, "15 48 3009 0001234")

    def test_compute_name_uses_customs_name_without_city(self):
        aduana = self.env["l10n_mx_catalogs.c_aduana"].create(
            {
                "code": "998",
                "name": "Customs Without City",
                "city": False,
                "state": "Test",
            }
        )
        pedimento = self.env["l10n_mx_cfdi.pedimento"].new(
            {
                "number": "15 48 3009 0001234",
                "customs_id": aduana,
                "date": False,
            }
        )
        pedimento._compute_name()
        self.assertIn("Customs Without City", pedimento.name)

    def test_valid_pedimento_number(self):
        pedimento = self._create_pedimento(number="15 48 3009 0001234")
        self.assertTrue(pedimento.id)

    def test_invalid_pedimento_number(self):
        with self.assertRaises(ValidationError):
            self._create_pedimento(number="invalid-number")
