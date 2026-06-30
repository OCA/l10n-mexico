from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, mute_logger

from .common import CFDITestMixin


class TestCFDIIssuer(CFDITestMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls._create_cfdi_service()
        cls.issuer = cls._create_cfdi_issuer(cls.service)

    def test_default_get_method(self):
        issuer = self.env["l10n_mx_cfdi.issuer"].default_get([])
        self.assertEqual(issuer["country_id"], self.env.ref("base.mx").id)

    def test_slugify_method(self):
        issuer = self.env["l10n_mx_cfdi.issuer"]
        self.assertEqual(issuer._slugify("Test String"), "test_string")

    def test_register_issuer_missing_service(self):
        self.issuer.service_id = False
        with self.assertRaises(UserError):
            self.issuer.register_issuer()

    def test_register_issuer_missing_vat(self):
        self.issuer.vat = False
        with self.assertRaises(UserError):
            self.issuer.register_issuer()

    def test_register_issuer_missing_certificate(self):
        self.issuer.certificate_file = False
        with self.assertRaises(UserError):
            self.issuer.register_issuer()

    def test_register_issuer_success(self):
        with patch.object(
            type(self.service),
            "register_csd",
            return_value=None,
        ):
            self.issuer.register_issuer()
        self.assertTrue(self.issuer.registered)

    @mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_issuer")
    def test_register_issuer_failure(self):
        with patch.object(
            type(self.service),
            "register_csd",
            side_effect=UserError("Registration failed"),
        ):
            with self.assertRaises(UserError):
                self.issuer.register_issuer()
        self.assertFalse(self.issuer.registered)

    def test_unregister_issuer_missing_certificate(self):
        self.issuer.certificate_file = False
        self.issuer.registered = True
        self.issuer.unregister_issuer()
        self.assertFalse(self.issuer.registered)

    def test_unregister_issuer_missing_service(self):
        self.issuer.service_id = False
        with self.assertRaises(UserError):
            self.issuer.unregister_issuer()

    def test_unregister_issuer_success(self):
        self.issuer.registered = True
        with patch.object(
            type(self.service),
            "unregister_csd",
            return_value=None,
        ):
            self.issuer.unregister_issuer()
        self.assertFalse(self.issuer.registered)

    @mute_logger("odoo.addons.l10n_mx_cfdi.models.cfdi_issuer")
    def test_unregister_issuer_failure(self):
        self.issuer.registered = True
        with patch.object(
            type(self.service),
            "unregister_csd",
            side_effect=UserError("Unregister failed"),
        ):
            with self.assertRaises(UserError):
                self.issuer.unregister_issuer()
