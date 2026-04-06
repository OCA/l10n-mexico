# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_mx_sat.services import SatClient

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
        """Retorna las credenciales FIEL decodificadas.

        :raises UserError: si falta algun campo
        :return: tupla (cer_der bytes, key_der bytes, password str)
        """
        self.ensure_one()
        if not self.l10n_mx_sat_fiel_cer:
            raise UserError(
                _("Suba el certificado FIEL (.cer) primero.")
            )
        if not self.l10n_mx_sat_fiel_key:
            raise UserError(
                _("Suba la llave privada FIEL (.key) primero.")
            )
        if not self.l10n_mx_sat_fiel_password:
            raise UserError(
                _("Ingrese la contrasena FIEL primero.")
            )
        try:
            cer_der = base64.b64decode(self.l10n_mx_sat_fiel_cer)
            key_der = base64.b64decode(self.l10n_mx_sat_fiel_key)
        except Exception as e:
            raise UserError(
                _("Error al decodificar credenciales FIEL: %s", e)
            ) from e
        return cer_der, key_der, self.l10n_mx_sat_fiel_password

    def l10n_mx_sat_get_client(self):
        """Factory: retorna instancia de SatClient.

        Sobreescribir este metodo para cambiar la implementacion
        del cliente SAT (por ejemplo, usar otra libreria).

        :raises UserError: si las credenciales son invalidas
        :return: instancia de SatClient
        """
        self.ensure_one()
        cer_der, key_der, password = self.l10n_mx_sat_get_credentials()
        try:
            return SatClient(cer_der, key_der, password)
        except Exception as e:
            raise UserError(
                _("Error al cargar credenciales FIEL: %s", e)
            ) from e

    def l10n_mx_sat_get_token(self):
        """Autentica con el SAT y retorna un token.

        :raises UserError: si la autenticacion falla
        :return: token de autenticacion SAT
        :rtype: str
        """
        self.ensure_one()
        client = self.l10n_mx_sat_get_client()
        try:
            return client.authenticate()
        except Exception as e:
            _logger.warning(
                "Autenticacion SAT fallo para %s: %s", self.name, e
            )
            raise UserError(
                _("Autenticacion SAT fallo: %s", e)
            ) from e

    def l10n_mx_sat_test_connection(self):
        """Boton para probar la conexion con el SAT.

        :return: accion de notificacion
        :rtype: dict
        """
        self.ensure_one()
        self.l10n_mx_sat_get_token()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Conexion SAT"),
                "message": _("Conexion exitosa. Token obtenido."),
                "type": "success",
                "sticky": False,
            },
        }
