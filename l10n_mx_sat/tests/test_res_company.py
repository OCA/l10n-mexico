# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from ..services import SatClient

MOCK_CER = base64.b64encode(b"fake-cer-content")
MOCK_KEY = base64.b64encode(b"fake-key-content")
MOCK_PASSWORD = "test-password"

_SVC = "odoo.addons.l10n_mx_sat.services.sat_client"
_WIZ_SVC = (
    "odoo.addons.l10n_mx_sat.wizards.l10n_mx_sat_fiel_credentials_wizard.SatClient"
)


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

    def test_invalid_base64_credentials_raise_user_error(self):
        self.company.write(
            {
                "l10n_mx_sat_fiel_cer": b"abc",
                "l10n_mx_sat_fiel_key": MOCK_KEY,
                "l10n_mx_sat_fiel_password": MOCK_PASSWORD,
            }
        )
        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_get_credentials()

    @patch(f"{_SVC}.Signer.load")
    @patch(f"{_SVC}.SAT")
    def test_get_client_returns_sat_client(self, mock_sat_cls, mock_signer_load):
        self._set_credentials()
        mock_signer_load.return_value.rfc = self.company.vat
        client = self.company.l10n_mx_sat_get_client()
        self.assertIsInstance(client, SatClient)
        mock_signer_load.assert_called_once()
        mock_sat_cls.assert_called_once()

    def test_get_rfc_uses_company_vat(self):
        self._set_credentials()
        client = MagicMock()
        client.rfc = "RFCFIEL123"
        self.assertEqual(self.company.l10n_mx_sat_get_rfc(client), "EKU9003173C9")

    @patch(f"{_SVC}.Signer.load")
    @patch(f"{_SVC}.SAT")
    def test_get_rfc_falls_back_to_fiel(self, mock_sat_cls, mock_signer_load):
        self._set_credentials()
        self.company.vat = False
        mock_signer_load.return_value.rfc = "RFCFIEL123"
        client = self.company.l10n_mx_sat_get_client()
        self.assertEqual(self.company.l10n_mx_sat_get_rfc(client), "RFCFIEL123")

    @patch("odoo.addons.l10n_mx_sat.models.res_company.SatClient")
    def test_get_client_exception_raises_user_error(self, MockSatClient):
        self._set_credentials()
        MockSatClient.side_effect = Exception("Invalid credentials")
        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_get_client()

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_get_token_returns_string(self, mock_signer_load, mock_sat_cls):
        self._set_credentials()
        mock_signer_load.return_value.rfc = self.company.vat
        mock_sat_cls.return_value._autentica_comprobante.return_value = {
            "AutenticaResult": "fake-token"
        }

        token = self.company.l10n_mx_sat_get_token()

        self.assertEqual(token, "fake-token")

    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_test_connection_success(self, mock_signer_load, mock_sat_cls):
        self._set_credentials()
        mock_signer_load.return_value.rfc = self.company.vat
        mock_sat_cls.return_value._autentica_comprobante.return_value = {
            "AutenticaResult": "fake-token"
        }

        result = self.company.l10n_mx_sat_test_connection()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["params"]["type"], "success")

    @mute_logger("odoo.addons.l10n_mx_sat.models.res_company")
    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_connection_exception_raises(self, mock_signer_load, mock_sat_cls):
        self._set_credentials()
        mock_signer_load.return_value.rfc = self.company.vat
        mock_sat_cls.return_value._autentica_comprobante.side_effect = Exception(
            "Network error"
        )

        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_test_connection()

    @mute_logger("odoo.addons.l10n_mx_sat.models.res_company")
    @patch(f"{_SVC}.SAT")
    @patch(f"{_SVC}.Signer.load")
    def test_empty_token_raises(self, mock_signer_load, mock_sat_cls):
        self._set_credentials()
        mock_signer_load.return_value.rfc = self.company.vat
        mock_sat_cls.return_value._autentica_comprobante.return_value = {
            "AutenticaResult": ""
        }

        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_test_connection()

    def test_get_xml_download_flows_default_four(self):
        flows = self.company.l10n_mx_sat_get_xml_download_flows()
        self.assertEqual(
            flows,
            [
                ("cfdi", "issued", "xml"),
                ("cfdi", "received", "xml"),
                ("retention", "issued", "xml"),
                ("retention", "received", "xml"),
            ],
        )

    @patch(f"{_SVC}.Signer.load")
    @patch(f"{_SVC}.SAT")
    def test_fiel_configured_status(self, mock_sat_cls, mock_signer_load):
        self._set_credentials()
        mock_signer_load.return_value.rfc = self.company.vat
        self.company.invalidate_recordset(
            [
                "l10n_mx_sat_fiel_configured",
                "l10n_mx_sat_fiel_certificate_configured",
                "l10n_mx_sat_fiel_key_configured",
                "l10n_mx_sat_fiel_rfc",
            ]
        )
        self.assertTrue(self.company.l10n_mx_sat_fiel_configured)
        self.assertTrue(self.company.l10n_mx_sat_fiel_certificate_configured)
        self.assertTrue(self.company.l10n_mx_sat_fiel_key_configured)
        self.assertEqual(self.company.l10n_mx_sat_fiel_rfc, self.company.vat)

    @patch(f"{_SVC}.Signer.load")
    @patch(f"{_SVC}.SAT")
    def test_fiel_wizard_updates_credentials(self, mock_sat_cls, mock_signer_load):
        mock_signer_load.return_value.rfc = "RFCFIEL123"
        self.company.vat = False
        with patch(_WIZ_SVC) as MockWizardClient:
            MockWizardClient.return_value.rfc = "RFCFIEL123"
            wizard = self.env["l10n_mx_sat.fiel.credentials.wizard"].create(
                {
                    "company_id": self.company.id,
                    "fiel_cer": MOCK_CER,
                    "fiel_key": MOCK_KEY,
                    "fiel_password": MOCK_PASSWORD,
                }
            )
            wizard.action_apply()
        self.assertTrue(self.company.l10n_mx_sat_has_credentials())
        self.assertEqual(self.company.l10n_mx_sat_fiel_password, MOCK_PASSWORD)
        self.assertEqual(self.company.vat, "RFCFIEL123")
        self.assertNotEqual(self.company.l10n_mx_sat_fiel_cer, False)
        self.assertNotEqual(self.company.l10n_mx_sat_fiel_key, False)

    def test_vat_cannot_change_when_fiel_configured(self):
        self._set_credentials()
        with self.assertRaises(UserError):
            self.company.write({"vat": "AAA010101AAA"})

    def test_sync_now_without_credentials_raises(self):
        self.company.write(
            {
                "l10n_mx_sat_fiel_cer": False,
                "l10n_mx_sat_fiel_key": False,
                "l10n_mx_sat_fiel_password": False,
            }
        )
        with self.assertRaises(UserError):
            self.company.l10n_mx_sat_sync_now()

    @patch(f"{_SVC}.Signer.load")
    @patch(f"{_SVC}.SAT")
    def test_sync_now_queues_background_processing(
        self, mock_sat_cls, mock_signer_load
    ):
        self._set_credentials()
        mock_signer_load.return_value.rfc = self.company.vat
        Request = self.env["l10n_mx_sat.download.request"]
        with (
            patch.object(type(Request), "_cron_trigger") as mock_trigger,
            patch.object(type(Request), "_cron_process_requests") as mock_cron,
        ):
            result = self.company.l10n_mx_sat_sync_now()
        pending = Request._parse_param_ids("l10n_mx_sat.sync_pending_company_ids")
        self.assertIn(self.company.id, pending)
        mock_trigger.assert_called_once()
        mock_cron.assert_not_called()
        self.assertEqual(result["params"]["type"], "info")
        self.assertIn("background", result["params"]["message"].lower())

    def test_action_view_documents_is_readonly(self):
        action = self.company.action_l10n_mx_sat_view_documents()
        self.assertEqual(action["res_model"], "l10n_mx_sat.document")
        self.assertEqual(action["domain"], [("company_id", "=", self.company.id)])
        self.assertFalse(action["context"]["create"])
        self.assertFalse(action["context"]["edit"])
        self.assertFalse(action["context"]["delete"])
        self.assertEqual(action["flags"], {"mode": "readonly"})

    def test_action_view_download_requests(self):
        action = self.company.action_l10n_mx_sat_view_download_requests()
        self.assertEqual(action["res_model"], "l10n_mx_sat.download.request")
        self.assertEqual(action["domain"], [("company_id", "=", self.company.id)])
        self.assertEqual(action["context"], {"default_company_id": self.company.id})

    def test_sat_document_and_request_counts(self):
        self.env.user.group_ids = [(4, self.env.ref("l10n_mx_sat.group_sat_user").id)]
        self.env["l10n_mx_sat.document"]._sat_create(
            [
                {
                    "company_id": self.company.id,
                    "uuid": "COUNT-UUID-123",
                    "document_kind": "cfdi",
                    "direction": "received",
                }
            ]
        )
        self.env["l10n_mx_sat.download.request"].create(
            {
                "company_id": self.company.id,
                "document_kind": "cfdi",
                "direction": "received",
                "request_type": "xml",
                "date_from": "2026-01-01 00:00:00",
                "date_to": "2026-01-31 23:59:59",
            }
        )

        self.company._compute_l10n_mx_sat_document_count()
        self.company._compute_l10n_mx_sat_download_request_count()

        self.assertEqual(self.company.l10n_mx_sat_document_count, 1)
        self.assertEqual(self.company.l10n_mx_sat_download_request_count, 1)

    def test_sat_counts_zero_without_sat_group(self):
        self.env["l10n_mx_sat.document"]._sat_create(
            [
                {
                    "company_id": self.company.id,
                    "uuid": "COUNT-NO-GROUP-UUID",
                    "document_kind": "cfdi",
                    "direction": "received",
                }
            ]
        )
        group_user = self.env.ref("l10n_mx_sat.group_sat_user")
        group_manager = self.env.ref("l10n_mx_sat.group_sat_manager")
        self.env.user.group_ids = [(3, group_user.id), (3, group_manager.id)]
        self.company._compute_l10n_mx_sat_document_count()
        self.company._compute_l10n_mx_sat_download_request_count()
        self.assertEqual(self.company.l10n_mx_sat_document_count, 0)
        self.assertEqual(self.company.l10n_mx_sat_download_request_count, 0)

    @patch(f"{_SVC}.Signer.load")
    @patch(f"{_SVC}.SAT")
    def test_get_client_rfc_mismatch_raises(self, mock_sat_cls, mock_signer_load):
        self._set_credentials()
        self.company.vat = "EKU9003173C9"
        mock_signer_load.return_value.rfc = "AAA010101AAA"
        with self.assertRaises(UserError) as err:
            self.company.l10n_mx_sat_get_client()
        self.assertIn("does not match", err.exception.args[0])

    def test_get_rfc_raises_when_unavailable(self):
        self.company.vat = False
        client = MagicMock()
        client.rfc = False
        with self.assertRaises(UserError) as err:
            self.company.l10n_mx_sat_get_rfc(client)
        self.assertIn("Could not determine the RFC", err.exception.args[0])

    def test_xml_download_flows_respects_flags(self):
        self.company.write(
            {
                "l10n_mx_sat_download_cfdi_issued": True,
                "l10n_mx_sat_download_cfdi_received": False,
                "l10n_mx_sat_download_retention_issued": False,
                "l10n_mx_sat_download_retention_received": True,
            }
        )
        flows = self.company.l10n_mx_sat_get_xml_download_flows()
        self.assertEqual(
            flows,
            [
                ("cfdi", "issued", "xml"),
                ("retention", "received", "xml"),
            ],
        )

    def test_vat_write_allowed_without_fiel(self):
        self.company.write(
            {
                "l10n_mx_sat_fiel_cer": False,
                "l10n_mx_sat_fiel_key": False,
                "l10n_mx_sat_fiel_password": False,
                "vat": "AAA010101AAA",
            }
        )
        self.assertEqual(self.company.vat, "AAA010101AAA")

    @patch(f"{_SVC}.Signer.load")
    @patch(f"{_SVC}.SAT")
    def test_fiel_status_when_client_fails(self, mock_sat_cls, mock_signer_load):
        self._set_credentials()
        mock_signer_load.side_effect = Exception("bad fiel")
        self.company.invalidate_recordset(
            [
                "l10n_mx_sat_fiel_configured",
                "l10n_mx_sat_fiel_rfc",
            ]
        )
        self.assertTrue(self.company.l10n_mx_sat_fiel_configured)
        self.assertFalse(self.company.l10n_mx_sat_fiel_rfc)
