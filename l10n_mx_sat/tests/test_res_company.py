# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

MOCK_CER = base64.b64encode(b"fake-cer-content")
MOCK_KEY = base64.b64encode(b"fake-key-content")
MOCK_PASSWORD = "test-password"

_SVC = "odoo.addons.l10n_mx_sat.services.sat_client"


@tagged("post_install", "-at_install")
class TestResCompanySATConnection(TransactionCase):
    """Test res.company SAT methods (factory, auth, test connection)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write(
            {
                "country_id": cls.env.ref("base.mx").id,
                "vat": "EKU9003173C9",
            }
        )

    def _set_credentials(self):
        self.company.write(
            {
                "l10n_mx_sat_fiel_cer": MOCK_CER,
                "l10n_mx_sat_fiel_key": MOCK_KEY,
                "l10n_mx_sat_fiel_password": MOCK_PASSWORD,
            }
        )

    def test_missing_certificate_raises(self):
        self.company.write(
            {
                "l10n_mx_sat_fiel_cer": False,
                "l10n_mx_sat_fiel_key": MOCK_KEY,
                "l10n_mx_sat_fiel_password": MOCK_PASSWORD,
            }
        )
        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_get_credentials()

    def test_missing_key_raises(self):
        self.company.write(
            {
                "l10n_mx_sat_fiel_cer": MOCK_CER,
                "l10n_mx_sat_fiel_key": False,
                "l10n_mx_sat_fiel_password": MOCK_PASSWORD,
            }
        )
        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_get_credentials()

    def test_missing_password_raises(self):
        self.company.write(
            {
                "l10n_mx_sat_fiel_cer": MOCK_CER,
                "l10n_mx_sat_fiel_key": MOCK_KEY,
                "l10n_mx_sat_fiel_password": False,
            }
        )
        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_get_credentials()

    def test_get_credentials_returns_decoded(self):
        self._set_credentials()
        cer, key, pwd = self.company.l10n_mx_sat_get_credentials()
        self.assertEqual(cer, b"fake-cer-content")
        self.assertEqual(key, b"fake-key-content")
        self.assertEqual(pwd, MOCK_PASSWORD)

    @patch(f"{_SVC}.Fiel")
    def test_get_client_returns_sat_client(self, MockFiel):
        from odoo.addons.l10n_mx_sat.services import SatClient

        self._set_credentials()
        client = self.company.l10n_mx_sat_get_client()
        self.assertIsInstance(client, SatClient)
        MockFiel.assert_called_once()

    @patch(f"{_SVC}.Autenticacion")
    @patch(f"{_SVC}.Fiel")
    def test_get_token_returns_string(self, MockFiel, MockAuth):
        self._set_credentials()
        MockAuth.return_value.obtener_token.return_value = "fake-token"

        token = self.company.l10n_mx_sat_get_token()

        self.assertEqual(token, "fake-token")

    @patch(f"{_SVC}.Autenticacion")
    @patch(f"{_SVC}.Fiel")
    def test_test_connection_success(self, MockFiel, MockAuth):
        self._set_credentials()
        MockAuth.return_value.obtener_token.return_value = "fake-token"

        result = self.company.l10n_mx_sat_test_connection()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["params"]["type"], "success")

    @patch(f"{_SVC}.Autenticacion")
    @patch(f"{_SVC}.Fiel")
    def test_connection_exception_raises(self, MockFiel, MockAuth):
        self._set_credentials()
        MockAuth.return_value.obtener_token.side_effect = Exception("Network error")

        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_test_connection()

    @patch(f"{_SVC}.Autenticacion")
    @patch(f"{_SVC}.Fiel")
    def test_empty_token_raises(self, MockFiel, MockAuth):
        self._set_credentials()
        MockAuth.return_value.obtener_token.return_value = ""

        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_test_connection()
