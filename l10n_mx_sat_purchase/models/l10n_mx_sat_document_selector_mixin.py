# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class L10nMxSatDocumentSelectorMixin(models.AbstractModel):
    """Let a record pick one of the received CFDIs downloaded from the SAT.

    The concrete model provides ``company_id`` and, optionally, ``partner_id``
    and ``currency_id``; the mixin restricts the selection to the CFDIs that
    can still be linked and validates the selected one.
    """

    _name = "l10n_mx_sat.document.selector.mixin"
    _description = "SAT CFDI selector"

    partner_id = fields.Many2one(comodel_name="res.partner")
    company_id = fields.Many2one(comodel_name="res.company")
    currency_id = fields.Many2one(comodel_name="res.currency")
    l10n_mx_sat_company_rfc = fields.Char(
        string="Company RFC", compute="_compute_l10n_mx_sat_selector"
    )
    l10n_mx_sat_issuer_rfc = fields.Char(
        string="Issuer RFC", compute="_compute_l10n_mx_sat_selector"
    )
    l10n_mx_sat_currency_name = fields.Char(
        string="Currency Code", related="currency_id.name"
    )
    l10n_mx_sat_has_document = fields.Boolean(
        string="Has SAT CFDIs to Link", compute="_compute_l10n_mx_sat_selector"
    )
    # Same conditions as l10n_mx_sat.document._get_selectable_domain, evaluated
    # by the client so the selection never loads the whole SAT archive.
    l10n_mx_sat_document_id = fields.Many2one(
        comodel_name="l10n_mx_sat.document",
        string="SAT CFDI",
        domain="["
        "('company_id', '=', company_id),"
        "('receiver_rfc', '=', l10n_mx_sat_company_rfc),"
        "('receiver_rfc', '!=', False),"
        "('document_kind', '=', 'cfdi'),"
        "('direction', '=', 'received'),"
        "('voucher_type', 'in', ['I', 'E']),"
        "('has_xml', '=', True),"
        "('sat_status', '!=', 'cancelled'),"
        "('vendor_bill_id', '=', False),"
        "]"
        " + ([('issuer_rfc', '=', l10n_mx_sat_issuer_rfc),"
        " ('issuer_rfc', '!=', False)] if partner_id else [])"
        " + ([('currency_code', '=', l10n_mx_sat_currency_name)]"
        " if currency_id else [])",
    )

    @api.depends(
        "partner_id.commercial_partner_id.vat", "company_id.vat", "currency_id"
    )
    def _compute_l10n_mx_sat_selector(self):
        Document = self.env["l10n_mx_sat.document"]
        for record in self:
            record.l10n_mx_sat_company_rfc = (
                (record.company_id.vat or "").strip().upper()
            )
            record.l10n_mx_sat_issuer_rfc = (
                (record.partner_id.commercial_partner_id.vat or "").strip().upper()
            )
            record.l10n_mx_sat_has_document = bool(
                Document.search(record._l10n_mx_sat_get_selectable_domain(), limit=1)
            )

    def _l10n_mx_sat_get_selectable_domain(self):
        self.ensure_one()
        return self.env["l10n_mx_sat.document"]._get_selectable_domain(
            self.company_id, self.partner_id, self.currency_id
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
        if not self.env["l10n_mx_sat.document"].search_count(
            self._l10n_mx_sat_get_selectable_domain() + [("id", "=", document.id)],
            limit=1,
        ):
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
