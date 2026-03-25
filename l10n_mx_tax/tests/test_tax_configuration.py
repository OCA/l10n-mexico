# Copyright 2025 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestTaxConfiguration(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        country_mx = cls.env.ref("base.mx")
        cls.company = cls.env["res.company"].create(
            {
                "name": "TestMX l10n_mx_tax",
                "country_id": country_mx.id,
                "currency_id": cls.env.ref("base.MXN").id,
            }
        )
        cls.env.user.company_ids |= cls.company
        cls.env.user.company_id = cls.company
        cls.env["account.chart.template"].try_loading(
            "mx",
            company=cls.company,
            install_demo=False,
        )
        cid = cls.company.id

        def ref(xml_id):
            return cls.env.ref(f"account.{cid}_{xml_id}", raise_if_not_found=False)

        cls._ref = staticmethod(ref)

    def test_ish_taxes_exist(self):
        """Verify ISH taxes were created correctly."""
        for rate in [
            "0",
            "0_5",
            "1",
            "1_5",
            "2",
            "2_5",
            "3",
            "3_5",
            "4",
            "4_5",
            "5",
        ]:
            for ttype in ["sale", "purchase"]:
                xml_id = f"ish_{rate}_{ttype}"
                tax = self._ref(xml_id)
                self.assertTrue(tax, f"ISH tax not found: {xml_id}")
                if tax:
                    self.assertEqual(tax.l10n_mx_tax_type, "local")
                    self.assertEqual(tax.tax_exigibility, "on_payment")

    def test_isn_taxes_exist(self):
        """Verify ISN taxes were created correctly."""
        for rate in ["1", "2", "3", "4"]:
            xml_id = f"isn_{rate}"
            tax = self._ref(xml_id)
            self.assertTrue(tax, f"ISN tax not found: {xml_id}")
            if tax:
                self.assertEqual(tax.type_tax_use, "none")

    def test_ieps_200_taxes_exist(self):
        """Verify IEPS 200% taxes were created correctly."""
        for ttype in ["sale", "purchase"]:
            xml_id = f"ieps_200_{ttype}"
            tax = self._ref(xml_id)
            self.assertTrue(tax, f"IEPS tax not found: {xml_id}")
            if tax:
                self.assertEqual(tax.amount, 200.0)
                self.assertEqual(tax.l10n_mx_tax_type, "ieps")
                self.assertEqual(tax.tax_exigibility, "on_payment")
                self.assertTrue(tax.include_base_amount)

    def test_accounts_exist(self):
        """Verify accounts were created correctly."""
        for xml_id in [
            "cuenta603_49_001",
            "cuenta603_29",
            "cuenta119_09_01",
        ]:
            acc = self._ref(xml_id)
            self.assertTrue(acc, f"Account not found: {xml_id}")

    def test_tax_groups_exist(self):
        """Verify tax groups were created correctly."""
        for xml_id in [
            "tax_group_ish",
            "tax_group_isn",
            "tax_group_ieps_200",
        ]:
            group = self._ref(xml_id)
            self.assertTrue(group, f"Tax group not found: {xml_id}")
