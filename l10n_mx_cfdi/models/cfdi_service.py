import json
import logging

import facturama

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CFDIService(models.Model):
    _name = "l10n_mx_cfdi.cfdi_service"
    _description = "CFDI Service Settings"

    name = fields.Char(required=True)
    company_ids = fields.Many2many(
        "res.company", string="Companies", default=lambda self: self.env.company
    )
    user = fields.Char(required=True, groups="base.group_system")
    password = fields.Char(required=True, groups="base.group_system")
    sandbox_mode = fields.Boolean(default=False, groups="base.group_system")
    stamps_available = fields.Integer(string="Stamps available", readonly=True)

    def _get_client(self):
        self.ensure_one()

        facturama.sandbox = True if self.sandbox_mode else False
        facturama._credentials = (self.user, self.password)
        return facturama

    def register_csd(
        self, rfc: str, cert_base64: bytes, key_base64: bytes, key_password: str
    ):
        self.ensure_one()

        client = self._get_client()
        try:
            client.csdsMultiEmisor.build_http_request(
                "post",
                "csds",
                {
                    "Rfc": str(rfc).upper(),
                    "Certificate": cert_base64.decode("utf-8"),
                    "PrivateKey": key_base64.decode("utf-8"),
                    "PrivateKeyPassword": key_password,
                },
                version=2,
            )
        except facturama.MalformedRequestError as e:
            error_message = str(e.error_json["Message"]) + "\n"
            if "ModelState" in e.error_json:
                model_state = e.error_json["ModelState"]
                for entry in model_state:
                    error_message += str(model_state[entry]) + "\n"
            raise UserError(error_message) from e

    def unregister_csd(self, rfc):
        self.ensure_one()

        client = self._get_client()
        client.csdsMultiEmisor.delete(rfc)

    def get_csd_status(self, rfc: str):
        self.ensure_one()

        client = self._get_client()
        return client.csdsMultiEmisor.get_by_rfc(rfc)

    def create_cfdi(self, cfdi_data: dict):
        self.ensure_one()
        client = self._get_client()
        try:
            res = client.CfdiMultiEmisor.build_http_request(
                "post", "cfdis", cfdi_data, version=6
            )
            if "Id" in res:
                _logger.info("CFDI creado: %s", res["Id"])
            return res
        except facturama.MalformedRequestError as e:
            error_message = self.env._(
                "Error when creating the CFDI: %s\n", e.error_json["Message"]
            )
            if "ModelState" in e.error_json:
                model_state = e.error_json["ModelState"]
                error_message += json.dumps(model_state, indent=4) + "\n"

            raise UserError(error_message) from e
        except facturama.ApiError as e:
            _logger.error(e)
            raise UserError(
                self.env._("Ocurrió un error con el servicio de facturación.\n")
            ) from e

    def get_cfdi_pdf(self, cfdi_id: str):
        client = self._get_client()
        return client.CfdiMultiEmisor.get_by_file("pdf", "IssuedLite", cfdi_id)

    def get_cfdi_xml(self, cfdi_id: str):
        client = self._get_client()
        return client.CfdiMultiEmisor.get_by_file("xml", "IssuedLite", cfdi_id)

    def cancel_cfdi(self, cfdi_id: str, reason, uuid_replacement):
        client = self._get_client()
        _logger.info("Cancelando CFDI %s", cfdi_id)
        return client.CfdiMultiEmisor.delete(cfdi_id, reason, uuid_replacement)

    def get_cancellation_request_proof(self, cfdi_id: str):
        client = self._get_client()
        res = client.CfdiMultiEmisor.build_http_request(
            "get", f"acuse/pdf/issuedLite/{cfdi_id}"
        )
        return res["Content"]

    def check_cfdi_status(self, uudi, issuer_rfc, receiver_rfc, amount_total):
        client = self._get_client()
        _logger.info("Consultando estado de CFDI %s", uudi)
        res = client.CfdiMultiEmisor.build_http_request(
            "get",
            "cfdi/status",
            params={
                "uuid": uudi,
                "issuerRfc": issuer_rfc,
                "receiverRfc": receiver_rfc,
                "total": amount_total,
            },
        )
        status = res["Status"]
        _logger.info("Estado de CFDI %s: %s", uudi, status)

        # mapping of status
        if status == "Vigente":
            return "published"

        if status == "Cancelado":
            return "cancelled"

        if status == "No Encontrado":
            return "unknown"
