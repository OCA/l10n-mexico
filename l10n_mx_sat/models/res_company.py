# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
import logging

from odoo import fields, models
from odoo.exceptions import UserError

from ..services import SatClient

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_sat_fiel_cer = fields.Binary(
        string="Certificado FIEL (.cer)",
        groups="base.group_system",
        attachment=False,
    )
    l10n_mx_sat_fiel_key = fields.Binary(
        string="Llave privada FIEL (.key)",
        groups="base.group_system",
        attachment=False,
    )
    l10n_mx_sat_fiel_password = fields.Char(
        string="Contrasena FIEL",
        groups="base.group_system",
    )

    def l10n_mx_sat_get_credentials(self):
        """Return decoded FIEL credentials.

        :raises UserError: if any credential field is missing
        :return: tuple (cer_der bytes, key_der bytes, password str)
        """
        self.ensure_one()
        if not self.l10n_mx_sat_fiel_cer:
            raise UserError(self.env._("Suba el certificado FIEL (.cer) primero."))
        if not self.l10n_mx_sat_fiel_key:
            raise UserError(self.env._("Suba la llave privada FIEL (.key) primero."))
        if not self.l10n_mx_sat_fiel_password:
            raise UserError(self.env._("Ingrese la contrasena FIEL primero."))
        try:
            cer_der = base64.b64decode(self.l10n_mx_sat_fiel_cer)
            key_der = base64.b64decode(self.l10n_mx_sat_fiel_key)
        except Exception as e:
            raise UserError(
                self.env._("Error al decodificar credenciales FIEL: %s", e)
            ) from e
        return cer_der, key_der, self.l10n_mx_sat_fiel_password

    def l10n_mx_sat_get_client(self):
        """Factory: return a SatClient instance.

        Override this method to swap the SAT client implementation
        (e.g. use a different library).

        :raises UserError: if credentials are invalid
        :return: SatClient instance
        """
        self.ensure_one()
        cer_der, key_der, password = self.l10n_mx_sat_get_credentials()
        try:
            return SatClient(cer_der, key_der, password)
        except Exception as e:
            raise UserError(
                self.env._("Error al cargar credenciales FIEL: %s", e)
            ) from e

    def l10n_mx_sat_get_token(self):
        """Authenticate with the SAT and return a token.

        :raises UserError: if authentication fails
        :return: SAT authentication token
        :rtype: str
        """
        self.ensure_one()
        client = self.l10n_mx_sat_get_client()
        try:
            return client.authenticate()
        except Exception as e:
            _logger.warning("SAT authentication failed for %s: %s", self.name, e)
            raise UserError(self.env._("Autenticacion SAT fallo: %s", e)) from e

    def l10n_mx_sat_test_connection(self):
        """Button to test the SAT connection.

        :return: notification action
        :rtype: dict
        """
        self.ensure_one()
        self.l10n_mx_sat_get_token()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Conexion SAT"),
                "message": self.env._("Conexion exitosa. Token obtenido."),
                "type": "success",
                "sticky": False,
            },
        }
