# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services import SatClient

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_sat_fiel_cer = fields.Binary(
        string="FIEL certificate (.cer)",
        groups="base.group_system",
        attachment=False,
    )
    l10n_mx_sat_fiel_key = fields.Binary(
        string="FIEL private key (.key)",
        groups="base.group_system",
        attachment=False,
    )
    l10n_mx_sat_fiel_password = fields.Char(
        string="FIEL password",
        groups="base.group_system",
    )
    l10n_mx_sat_sync_from = fields.Date(
        string="Sync documents from",
        help="Initial date for the first bulk XML download. "
        "After the first successful sync, the system continues "
        "incrementally from the last completed range.",
    )
    l10n_mx_sat_metadata_sync_from = fields.Date(
        string="Sync metadata from",
        help="Initial date for bulk metadata download (SAT status). "
        "If empty, the same date as XML sync is used.",
    )
    l10n_mx_sat_last_sync = fields.Datetime(
        string="Last XML sync",
        readonly=True,
    )
    l10n_mx_sat_last_metadata_sync = fields.Datetime(
        string="Last metadata sync",
        readonly=True,
    )
    l10n_mx_sat_auto_download = fields.Boolean(
        string="Automatic SAT download",
        default=True,
        help="Enables daily creation and processing of bulk download "
        "requests for this company.",
    )
    l10n_mx_sat_download_cfdi_issued = fields.Boolean(
        string="Download issued CFDIs",
        default=True,
    )
    l10n_mx_sat_download_cfdi_received = fields.Boolean(
        string="Download received CFDIs",
        default=True,
    )
    l10n_mx_sat_download_retention_issued = fields.Boolean(
        string="Download issued retentions",
        default=True,
    )
    l10n_mx_sat_download_retention_received = fields.Boolean(
        string="Download received retentions",
        default=True,
    )
    l10n_mx_sat_fiel_configured = fields.Boolean(
        string="FIEL configured",
        compute="_compute_l10n_mx_sat_fiel_status",
    )
    l10n_mx_sat_fiel_certificate_configured = fields.Boolean(
        string="FIEL certificate configured",
        compute="_compute_l10n_mx_sat_fiel_status",
    )
    l10n_mx_sat_fiel_key_configured = fields.Boolean(
        string="Llave FIEL configured",
        compute="_compute_l10n_mx_sat_fiel_status",
    )
    l10n_mx_sat_fiel_rfc = fields.Char(
        string="RFC FIEL",
        compute="_compute_l10n_mx_sat_fiel_status",
    )
    l10n_mx_sat_document_count = fields.Integer(
        string="SAT documents",
        compute="_compute_l10n_mx_sat_document_count",
    )
    l10n_mx_sat_download_request_count = fields.Integer(
        string="SAT download requests",
        compute="_compute_l10n_mx_sat_download_request_count",
    )

    @api.depends(
        "l10n_mx_sat_fiel_cer",
        "l10n_mx_sat_fiel_key",
        "l10n_mx_sat_fiel_password",
    )
    def _compute_l10n_mx_sat_fiel_status(self):
        for company in self:
            company.l10n_mx_sat_fiel_certificate_configured = bool(
                company.l10n_mx_sat_fiel_cer
            )
            company.l10n_mx_sat_fiel_key_configured = bool(company.l10n_mx_sat_fiel_key)
            company.l10n_mx_sat_fiel_configured = company.l10n_mx_sat_has_credentials()
            company.l10n_mx_sat_fiel_rfc = False
            if company.l10n_mx_sat_fiel_configured:
                try:
                    client = company.l10n_mx_sat_get_client()
                    company.l10n_mx_sat_fiel_rfc = client.rfc
                except Exception:
                    company.l10n_mx_sat_fiel_rfc = False

    def l10n_mx_sat_get_xml_download_flows(self):
        """Return enabled XML download flows for this company."""
        self.ensure_one()
        flows = []
        if self.l10n_mx_sat_download_cfdi_issued:
            flows.append(("cfdi", "issued", "xml"))
        if self.l10n_mx_sat_download_cfdi_received:
            flows.append(("cfdi", "received", "xml"))
        if self.l10n_mx_sat_download_retention_issued:
            flows.append(("retention", "issued", "xml"))
        if self.l10n_mx_sat_download_retention_received:
            flows.append(("retention", "received", "xml"))
        return flows

    def _compute_l10n_mx_sat_document_count(self):
        if not self.env.user.has_group("l10n_mx_sat.group_sat_user"):
            for company in self:
                company.l10n_mx_sat_document_count = 0
            return
        grouped = self.env["l10n_mx_sat.document"]._read_group(
            domain=[("company_id", "in", self.ids)],
            groupby=["company_id"],
            aggregates=["__count"],
        )
        counts = {company.id: count for company, count in grouped}
        for company in self:
            company.l10n_mx_sat_document_count = counts.get(company.id, 0)

    def _compute_l10n_mx_sat_download_request_count(self):
        if not self.env.user.has_group("l10n_mx_sat.group_sat_user"):
            for company in self:
                company.l10n_mx_sat_download_request_count = 0
            return
        grouped = self.env["l10n_mx_sat.download.request"]._read_group(
            domain=[("company_id", "in", self.ids)],
            groupby=["company_id"],
            aggregates=["__count"],
        )
        counts = {company.id: count for company, count in grouped}
        for company in self:
            company.l10n_mx_sat_download_request_count = counts.get(company.id, 0)

    def write(self, vals):
        if "vat" in vals and not self.env.context.get("l10n_mx_sat_sync_vat_from_fiel"):
            new_vat = (vals.get("vat") or "").strip().upper()
            for company in self:
                if not company.l10n_mx_sat_has_credentials():
                    continue
                current_vat = (company.vat or "").strip().upper()
                if new_vat and new_vat != current_vat:
                    raise UserError(
                        self.env._(
                            "You cannot change the company RFC/VAT while FIEL "
                            "credentials are configured. Update the FIEL to change it."
                        )
                    )
        return super().write(vals)

    def l10n_mx_sat_get_credentials(self):
        """Return decoded FIEL credentials."""
        self.ensure_one()
        if not self.l10n_mx_sat_fiel_cer:
            raise UserError(self.env._("Upload the FIEL certificate (.cer) first."))
        if not self.l10n_mx_sat_fiel_key:
            raise UserError(self.env._("Upload the FIEL private key (.key) first."))
        if not self.l10n_mx_sat_fiel_password:
            raise UserError(self.env._("Enter the FIEL password first."))
        try:
            cer_der = base64.b64decode(self.l10n_mx_sat_fiel_cer)
            key_der = base64.b64decode(self.l10n_mx_sat_fiel_key)
        except Exception as e:
            raise UserError(
                self.env._("Failed to decode FIEL credentials: %s", e)
            ) from e
        return cer_der, key_der, self.l10n_mx_sat_fiel_password

    def l10n_mx_sat_get_client(self):
        """Factory: return a SatClient instance."""
        self.ensure_one()
        cer_der, key_der, password = self.l10n_mx_sat_get_credentials()
        try:
            client = SatClient(cer_der, key_der, password)
            self._l10n_mx_sat_validate_fiel_rfc(client)
            return client
        except UserError:
            raise
        except Exception as e:
            raise UserError(self.env._("Failed to load FIEL credentials: %s", e)) from e

    def _l10n_mx_sat_validate_fiel_rfc(self, client):
        """Ensure FIEL RFC matches company VAT when both are set."""
        self.ensure_one()
        if not self.vat or not client.rfc:
            return
        company_rfc = self.vat.strip().upper()
        fiel_rfc = client.rfc.strip().upper()
        if company_rfc != fiel_rfc:
            raise UserError(
                self.env._(
                    "The FIEL certificate RFC (%(fiel)s) does not match "
                    "the company RFC (%(company)s).",
                    fiel=fiel_rfc,
                    company=company_rfc,
                )
            )

    def l10n_mx_sat_get_rfc(self, client=None):
        """Return the RFC used for SAT download requests."""
        self.ensure_one()
        if self.vat:
            return self.vat.strip().upper()
        if client is None:
            client = self.l10n_mx_sat_get_client()
        if client.rfc:
            return client.rfc.strip().upper()
        raise UserError(
            self.env._(
                "Could not determine the RFC. Set the company RFC/VAT or "
                "verify the FIEL certificate."
            )
        )

    def l10n_mx_sat_has_credentials(self):
        self.ensure_one()
        return bool(
            self.l10n_mx_sat_fiel_cer
            and self.l10n_mx_sat_fiel_key
            and self.l10n_mx_sat_fiel_password
        )

    def l10n_mx_sat_get_token(self):
        """Authenticate with the SAT and return a token."""
        self.ensure_one()
        client = self.l10n_mx_sat_get_client()
        try:
            return client.authenticate()
        except Exception as e:
            _logger.warning("SAT authentication failed for %s: %s", self.name, e)
            raise UserError(self.env._("SAT authentication failed: %s", e)) from e

    def action_l10n_mx_sat_open_fiel_wizard(self):
        """Open wizard to upload new FIEL credentials."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Update FIEL credentials"),
            "res_model": "l10n_mx_sat.fiel.credentials.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_company_id": self.id},
        }

    def l10n_mx_sat_test_connection(self):
        """Button to test the SAT connection."""
        self.ensure_one()
        self.l10n_mx_sat_get_token()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("SAT connection"),
                "message": self.env._("Connection successful. Token obtained."),
                "type": "success",
                "sticky": False,
            },
        }

    def l10n_mx_sat_sync_now(self):
        """Manual trigger for SAT download and metadata sync."""
        self.ensure_one()
        if not self.l10n_mx_sat_has_credentials():
            raise UserError(
                self.env._(
                    "Configure FIEL credentials before starting SAT synchronization."
                )
            )
        self.l10n_mx_sat_get_client()
        Request = self.env["l10n_mx_sat.download.request"]
        Request._mark_company_sync_pending(self)
        Request._cron_trigger()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("SAT synchronization"),
                "message": self.env._(
                    "Synchronization scheduled in the background. "
                    "Review SAT download requests to monitor progress."
                ),
                "type": "info",
                "sticky": True,
            },
        }

    def action_l10n_mx_sat_view_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("SAT documents"),
            "res_model": "l10n_mx_sat.document",
            "view_mode": "list,form",
            "domain": [("company_id", "=", self.id)],
            "context": {
                "default_company_id": self.id,
                "create": False,
                "edit": False,
                "delete": False,
            },
            "flags": {"mode": "readonly"},
        }

    def action_l10n_mx_sat_view_download_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("SAT download requests"),
            "res_model": "l10n_mx_sat.download.request",
            "view_mode": "list,form",
            "domain": [("company_id", "=", self.id)],
            "context": {"default_company_id": self.id},
        }
