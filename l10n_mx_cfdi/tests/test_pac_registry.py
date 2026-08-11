from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from satcfdi.pacs import Environment

from odoo.tests.common import TransactionCase

from odoo.addons.l10n_mx_cfdi.services import pac_registry


class TestPACRegistry(TransactionCase):
    def _service(self, **extra):
        vals = {
            "user": "user",
            "password": "pass",
            "pac_rfc": "RFC123",
            "pac_client_id": "client",
            "pac_token": "",
            "pac_contrato": "ctr",
            "pac_requestor": "req",
            "pac_country": "",
            "sandbox_mode": True,
            "provider": "finkok",
        }
        vals.update(extra)
        return SimpleNamespace(**vals)

    def test_get_provider_unknown_raises(self):
        with self.assertRaises(KeyError) as ctx:
            pac_registry.get_provider("unknown-pac")
        self.assertIn("Unknown PAC provider", str(ctx.exception))

    def test_provider_selection(self):
        selection = pac_registry.provider_selection()
        codes = [code for code, _label in selection]
        self.assertIn("finkok", codes)
        self.assertEqual(len(selection), len(pac_registry.PAC_PROVIDERS))

    def test_env_sandbox_vs_production(self):
        self.assertEqual(pac_registry._env(True), Environment.TEST)
        self.assertEqual(pac_registry._env(False), Environment.PRODUCTION)

    def test_diverza_kwargs(self):
        service = self._service(password="tok")
        kwargs = pac_registry.get_provider("diverza").kwargs_builder(
            service, Environment.TEST
        )
        self.assertEqual(kwargs["rfc"], "RFC123")
        self.assertEqual(kwargs["id"], "client")
        self.assertEqual(kwargs["token"], "tok")

    def test_diverza_kwargs_falls_back_to_pac_token(self):
        service = self._service(password="", pac_token="from-token")
        kwargs = pac_registry.get_provider("diverza").kwargs_builder(
            service, Environment.TEST
        )
        self.assertEqual(kwargs["token"], "from-token")

    def test_swsapien_kwargs_token_vs_user_password(self):
        with_token = self._service(pac_token="abc")
        kwargs = pac_registry.get_provider("swsapien").kwargs_builder(
            with_token, Environment.TEST
        )
        self.assertEqual(kwargs["token"], "abc")
        self.assertNotIn("user", kwargs)

        without_token = self._service(pac_token="")
        kwargs = pac_registry.get_provider("swsapien").kwargs_builder(
            without_token, Environment.PRODUCTION
        )
        self.assertEqual(kwargs["user"], "user")
        self.assertEqual(kwargs["password"], "pass")
        self.assertNotIn("token", kwargs)

    def test_mysuite_kwargs_default_country(self):
        service = self._service(pac_country="")
        kwargs = pac_registry.get_provider("mysuite").kwargs_builder(
            service, Environment.TEST
        )
        self.assertEqual(kwargs["country"], "MX")
        self.assertEqual(kwargs["requestor"], "req")

    def test_prodigia_and_comerciodigital_kwargs(self):
        service = self._service()
        prodigia = pac_registry.get_provider("prodigia").kwargs_builder(
            service, Environment.TEST
        )
        self.assertEqual(prodigia["contrato"], "ctr")
        comercio = pac_registry.get_provider("comerciodigital").kwargs_builder(
            service, Environment.TEST
        )
        self.assertEqual(comercio["user"], "user")
        self.assertEqual(comercio["password"], "pass")

    def test_facturama_kwargs_and_capabilities(self):
        service = self._service(provider="facturama")
        provider = pac_registry.get_provider("facturama")
        kwargs = provider.kwargs_builder(service, Environment.TEST)
        self.assertEqual(kwargs["username"], "user")
        self.assertEqual(kwargs["password"], "pass")
        self.assertEqual(kwargs["environment"], Environment.TEST)
        self.assertTrue(provider.supports_issue)
        self.assertTrue(provider.supports_cancel)
        self.assertFalse(provider.requires_signer_for_cancel)

    def test_build_pac_imports_and_instantiates(self):
        service = self._service(provider="finkok", sandbox_mode=True)
        fake_cls = MagicMock(return_value="pac-instance")
        fake_module = MagicMock()
        fake_module.Finkok = fake_cls
        with patch("importlib.import_module", return_value=fake_module) as mock_import:
            result = pac_registry.build_pac(service)
        mock_import.assert_called_once_with("satcfdi.pacs.finkok")
        fake_cls.assert_called_once()
        self.assertEqual(result, "pac-instance")
        kwargs = fake_cls.call_args.kwargs
        self.assertEqual(kwargs["username"], "user")
        self.assertEqual(kwargs["environment"], Environment.TEST)

    def test_build_pac_facturama(self):
        service = self._service(provider="facturama", sandbox_mode=False)
        fake_pac = MagicMock(name="facturama-pac")
        fake_cls = MagicMock(return_value=fake_pac)
        fake_module = MagicMock()
        fake_module.Facturama = fake_cls
        with patch("importlib.import_module", return_value=fake_module) as mock_import:
            result = pac_registry.build_pac(service)
        mock_import.assert_called_once_with("satcfdi.pacs.facturama")
        self.assertIs(result, fake_pac)
        # Odoo wraps issue()/cancel() for NameId, pedimentos, cancel Message
        self.assertTrue(callable(result.issue))
        self.assertTrue(callable(result.cancel))
        kwargs = fake_cls.call_args.kwargs
        self.assertEqual(kwargs["username"], "user")
        self.assertEqual(kwargs["password"], "pass")
        self.assertEqual(kwargs["environment"], Environment.PRODUCTION)
