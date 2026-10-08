# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class L10nMxSatDocumentSelectorMixin(models.AbstractModel):
    """Let a record pick one of the received CFDIs downloaded from the SAT.

    The concrete model provides ``company_id`` and, optionally, ``partner_id``
    and ``currency_id``; the mixin computes the CFDIs that can still be linked
    and validates the selected one.
    """

    _name = "l10n_mx_sat.document.selector.mixin"
    _description = "SAT CFDI selector"

    partner_id = fields.Many2one(comodel_name="res.partner")
    company_id = fields.Many2one(comodel_name="res.company")
    currency_id = fields.Many2one(comodel_name="res.currency")
    l10n_mx_sat_document_id = fields.Many2one(
        comodel_name="l10n_mx_sat.document",
        string="SAT CFDI",
        domain="[('id', 'in', l10n_mx_sat_available_document_ids)]",
    )
    l10n_mx_sat_available_document_ids = fields.Many2many(
        comodel_name="l10n_mx_sat.document",
        string="Available SAT CFDIs",
        compute="_compute_l10n_mx_sat_available_document_ids",
    )

    @api.depends("partner_id", "company_id", "currency_id")
    def _compute_l10n_mx_sat_available_document_ids(self):
        Document = self.env["l10n_mx_sat.document"]
        for record in self:
            if not record.company_id:
                record.l10n_mx_sat_available_document_ids = False
                continue
            record.l10n_mx_sat_available_document_ids = Document.search(
                Document._get_selectable_domain(
                    record.company_id, record.partner_id, record.currency_id
                )
            )

    def _l10n_mx_sat_check_document(self):
        """Return the reason why the selected CFDI cannot be used, or False.

        Rejections are returned instead of raised so the caller can keep the
        changes made during the check (e.g. a SAT status refresh).
        """
        self.ensure_one()
        document = self.l10n_mx_sat_document_id
        if not document:
            return self.env._("Select a CFDI downloaded from the SAT.")
        if document not in self.l10n_mx_sat_available_document_ids:
            return self.env._(
                "The CFDI %(uuid)s can no longer be linked: it was cancelled, "
                "linked to another vendor bill or does not belong to the vendor.",
                uuid=document.uuid,
            )
        return False

    def _l10n_mx_sat_rejection_action(self, message):
        """Action to show ``message`` returned by ``_l10n_mx_sat_check_document``."""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("SAT CFDI"),
                "message": message,
                "type": "danger",
                "sticky": True,
            },
        }
