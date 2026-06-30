# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

MOCK_CER = base64.b64encode(b"fake-cer-content")
MOCK_KEY = base64.b64encode(b"fake-key-content")
MOCK_PASSWORD = "test-password"

_WIZ_SVC = (
    "odoo.addons.l10n_mx_sat.wizards.l10n_mx_sat_fiel_credentials_wizard.SatClient"
)


@tagged("post_install", "-at_install")
class TestFielCredentialsWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({"country_id": cls.env.ref("base.mx").id})

    def test_wizard_starts_empty_even_with_existing_credentials(self):
        self.company.write(
            {
                "l10n_mx_sat_fiel_cer": MOCK_CER,
                "l10n_mx_sat_fiel_key": MOCK_KEY,
                "l10n_mx_sat_fiel_password": MOCK_PASSWORD,
            }
        )
        wizard = self.env["l10n_mx_sat.fiel.credentials.wizard"].create(
            {"company_id": self.company.id}
        )
        self.assertFalse(wizard.fiel_cer)
        self.assertFalse(wizard.fiel_key)
        self.assertFalse(wizard.fiel_password)

    def test_wizard_requires_all_fields(self):
        wizard = self.env["l10n_mx_sat.fiel.credentials.wizard"].create(
            {"company_id": self.company.id}
        )
        with self.assertRaises(UserError) as err:
            wizard.action_apply()
        self.assertIn("certificate", err.exception.args[0].lower())

    def test_wizard_requires_key(self):
        wizard = self.env["l10n_mx_sat.fiel.credentials.wizard"].create(
            {
                "company_id": self.company.id,
                "fiel_cer": MOCK_CER,
            }
        )
        with self.assertRaises(UserError) as err:
            wizard.action_apply()
        self.assertIn("private key", err.exception.args[0].lower())

    def test_wizard_requires_password(self):
        wizard = self.env["l10n_mx_sat.fiel.credentials.wizard"].create(
            {
                "company_id": self.company.id,
                "fiel_cer": MOCK_CER,
                "fiel_key": MOCK_KEY,
            }
        )
        with self.assertRaises(UserError) as err:
            wizard.action_apply()
        self.assertIn("password", err.exception.args[0].lower())

    def test_open_fiel_wizard_action(self):
        action = self.company.action_l10n_mx_sat_open_fiel_wizard()
        self.assertEqual(action["res_model"], "l10n_mx_sat.fiel.credentials.wizard")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_company_id"], self.company.id)

    @patch(_WIZ_SVC)
    def test_wizard_sets_company_vat_from_fiel(self, MockSatClient):
        mock_client = MockSatClient.return_value
        mock_client.rfc = "RFCFIEL123"
        self.company.vat = False
        wizard = self.env["l10n_mx_sat.fiel.credentials.wizard"].create(
            {
                "company_id": self.company.id,
                "fiel_cer": MOCK_CER,
                "fiel_key": MOCK_KEY,
                "fiel_password": MOCK_PASSWORD,
            }
        )
        wizard.action_apply()
        self.assertEqual(self.company.vat, "RFCFIEL123")
        self.assertTrue(self.company.l10n_mx_sat_has_credentials())

    @patch(_WIZ_SVC)
    def test_wizard_normalizes_fiel_rfc(self, MockSatClient):
        MockSatClient.return_value.rfc = "  abc010101xyz  "
        self.company.vat = False
        wizard = self.env["l10n_mx_sat.fiel.credentials.wizard"].create(
            {
                "company_id": self.company.id,
                "fiel_cer": MOCK_CER,
                "fiel_key": MOCK_KEY,
                "fiel_password": MOCK_PASSWORD,
            }
        )
        wizard.action_apply()
        self.assertEqual(self.company.vat, "ABC010101XYZ")

    @patch(_WIZ_SVC)
    def test_wizard_empty_rfc_raises(self, MockSatClient):
        MockSatClient.return_value.rfc = ""
        wizard = self.env["l10n_mx_sat.fiel.credentials.wizard"].create(
            {
                "company_id": self.company.id,
                "fiel_cer": MOCK_CER,
                "fiel_key": MOCK_KEY,
                "fiel_password": MOCK_PASSWORD,
            }
        )
        with self.assertRaises(UserError) as err:
            wizard.action_apply()
        self.assertIn("rfc", err.exception.args[0].lower())

    @patch(_WIZ_SVC)
    def test_wizard_satcfdi_exception_raises_user_error(self, MockSatClient):
        MockSatClient.side_effect = Exception("bad key")
        wizard = self.env["l10n_mx_sat.fiel.credentials.wizard"].create(
            {
                "company_id": self.company.id,
                "fiel_cer": MOCK_CER,
                "fiel_key": MOCK_KEY,
                "fiel_password": MOCK_PASSWORD,
            }
        )
        with self.assertRaises(UserError) as err:
            wizard.action_apply()
        self.assertIn("Failed to validate FIEL", err.exception.args[0])
