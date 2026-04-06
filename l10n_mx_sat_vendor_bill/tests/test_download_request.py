# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import timedelta
from unittest.mock import MagicMock, patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDownloadRequest(TransactionCase):
    """Test the SAT download request state machine."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.company.write(
            {
                "vat": "EKU9003173C9",
                "country_id": cls.env.ref("base.mx").id,
                "l10n_mx_sat_fiel_cer": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_key": b"ZmFrZQ==",
                "l10n_mx_sat_fiel_password": "test",
            }
        )

    def _create_request(self, **kwargs):
        vals = {
            "company_id": self.company.id,
            "fecha_inicial": "2026-02-01 00:00:00",
            "fecha_final": "2026-02-28 23:59:59",
            "state": "draft",
        }
        vals.update(kwargs)
        return self.env["l10n_mx_sat.download.request"].create(vals)

    def _mock_client(self, **overrides):
        """Return a MagicMock that behaves like SatClient."""
        client = MagicMock()
        client.authenticate.return_value = "fake-token"
        for attr, val in overrides.items():
            setattr(client, attr, val)
        return client

    def _patch_factory(self, mock_client):
        """Patch l10n_mx_sat_get_client on the company model."""
        return patch.object(
            type(self.company),
            "l10n_mx_sat_get_client",
            return_value=mock_client,
        )

    # ------------------------------------------------------------------
    # _action_request
    # ------------------------------------------------------------------

    def test_action_request_success(self):
        """draft -> requested on successful SAT request."""
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": "5000",
            "id_solicitud": "SOL-12345",
            "mensaje": "Solicitud aceptada",
        }

        req = self._create_request()
        with self._patch_factory(client):
            req._action_request()

        self.assertEqual(req.state, "requested")
        self.assertEqual(req.id_solicitud, "SOL-12345")

    def test_action_request_no_data(self):
        """draft -> done on cod_estatus 5004 (no data found)."""
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": "5004",
            "id_solicitud": "",
            "mensaje": "No se encontro informacion",
        }

        req = self._create_request()
        with self._patch_factory(client):
            req._action_request()

        self.assertEqual(req.state, "done")
        self.assertEqual(req.cfdi_count, 0)

    def test_action_request_accepted_5004_with_request_id(self):
        """5004 + id_solicitud (p. ej. int) debe pasar a requested."""
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": 5004,
            "id_solicitud": "SOL-5004",
            "mensaje": "Solicitud Aceptada",
        }

        req = self._create_request()
        with self._patch_factory(client):
            req._action_request()

        self.assertEqual(req.state, "requested")
        self.assertEqual(req.id_solicitud, "SOL-5004")

    def test_action_request_error(self):
        """draft -> error on rejected request."""
        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": "5005",
            "id_solicitud": "",
            "mensaje": "Solicitud duplicada",
        }

        req = self._create_request()
        with self._patch_factory(client):
            req._action_request()

        self.assertEqual(req.state, "error")
        self.assertIn("5005", req.error_message)

    # ------------------------------------------------------------------
    # _action_verify
    # ------------------------------------------------------------------

    def test_action_verify_processing(self):
        """requested -> processing when SAT is still working."""
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": "5000",
            "estado_solicitud": "2",
            "codigo_estado_solicitud": "5000",
            "numero_cfdis": "5",
            "mensaje": "En proceso",
            "paquetes": [],
        }

        req = self._create_request(state="requested", id_solicitud="SOL-123")
        with self._patch_factory(client):
            req._action_verify()

        self.assertEqual(req.state, "processing")
        self.assertEqual(req.numero_cfdis, 5)

    def test_action_verify_ready(self):
        """requested -> ready when packages are available."""
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": "5000",
            "estado_solicitud": "3",
            "codigo_estado_solicitud": "5000",
            "numero_cfdis": "1",
            "mensaje": "Terminada",
            "paquetes": ["PKG-001", "PKG-002"],
        }

        req = self._create_request(state="requested", id_solicitud="SOL-123")
        with self._patch_factory(client):
            req._action_verify()

        self.assertEqual(req.state, "ready")
        self.assertEqual(len(req.package_ids), 2)
        self.assertEqual(req.package_ids[0].id_paquete, "PKG-001")
        self.assertEqual(req.package_ids[1].id_paquete, "PKG-002")

    def test_action_verify_error(self):
        """requested -> error on rejected/expired request."""
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": "5000",
            "estado_solicitud": "4",
            "codigo_estado_solicitud": "5004",
            "numero_cfdis": "0",
            "mensaje": "Error en la solicitud",
            "paquetes": [],
        }

        req = self._create_request(state="requested", id_solicitud="SOL-123")
        with self._patch_factory(client):
            req._action_verify()

        self.assertEqual(req.state, "error")
        self.assertIn("SAT verification", req.error_message)
        self.assertIn("5004", req.error_message)

    def test_action_verify_cod_estatus_5004_keeps_processing(self):
        """Verificación CodEstatus 5004: reintentar en siguiente cron."""
        client = self._mock_client()
        client.verify_download.return_value = {
            "cod_estatus": "5004",
            "estado_solicitud": "0",
            "codigo_estado_solicitud": "",
            "numero_cfdis": "0",
            "mensaje": "No se encontró la información",
            "paquetes": [],
        }

        req = self._create_request(state="requested", id_solicitud="SOL-123")
        with self._patch_factory(client):
            req._action_verify()

        self.assertEqual(req.state, "processing")

    # ------------------------------------------------------------------
    # _create_next_request
    # ------------------------------------------------------------------

    def test_create_next_request_default_30_days(self):
        """Without sync_from or last_done, should default to 30 days ago."""
        self.company.write(
            {
                "l10n_mx_sat_vendor_bill_sync_from": False,
                "l10n_mx_sat_vendor_bill_last_sync": False,
            }
        )
        self.env["l10n_mx_sat.download.request"].search(
            [("company_id", "=", self.company.id)]
        ).unlink()

        req = self.env["l10n_mx_sat.download.request"]._create_next_request(
            self.company
        )

        self.assertTrue(req, "Should create a request")
        self.assertEqual(req.state, "draft")
        self.assertTrue(req.fecha_final)

    def test_create_next_request_from_sync_date(self):
        """With sync_from configured, should use that date."""
        self.company.write(
            {
                "l10n_mx_sat_vendor_bill_sync_from": "2026-01-01",
                "l10n_mx_sat_vendor_bill_last_sync": False,
            }
        )
        self.env["l10n_mx_sat.download.request"].search(
            [("company_id", "=", self.company.id)]
        ).unlink()

        req = self.env["l10n_mx_sat.download.request"]._create_next_request(
            self.company
        )

        self.assertTrue(req)
        self.assertEqual(req.fecha_inicial.date().isoformat(), "2026-01-01")

    def test_create_next_request_chains_from_last_done(self):
        """After a completed request, next one starts after its fecha_final."""
        self.env["l10n_mx_sat.download.request"].search(
            [("company_id", "=", self.company.id)]
        ).unlink()

        done_req = self._create_request(
            fecha_inicial="2026-01-01 00:00:00",
            fecha_final="2026-01-31 23:59:59",
            state="done",
        )

        req = self.env["l10n_mx_sat.download.request"]._create_next_request(
            self.company
        )

        self.assertTrue(req)
        self.assertEqual(req.fecha_inicial, done_req.fecha_final + timedelta(seconds=1))

    def test_cron_does_not_autochain_after_error(self):
        """Tras error en solicitud, no debe crearse un segundo draft automático."""
        self.env["l10n_mx_sat.download.request"].search(
            [("company_id", "=", self.company.id)]
        ).unlink()
        self.company.write({"l10n_mx_sat_vendor_bill_sync_from": "2026-01-01"})

        client = self._mock_client()
        client.request_download.return_value = {
            "cod_estatus": "5005",
            "id_solicitud": "",
            "mensaje": "Solicitud duplicada",
        }

        with self._patch_factory(client):
            self.env["l10n_mx_sat.download.request"].with_context(
                test_queue_job_no_delay=True
            )._cron_process_requests(companies=self.company)

        requests = self.env["l10n_mx_sat.download.request"].search(
            [("company_id", "=", self.company.id)]
        )
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests.state, "error")
