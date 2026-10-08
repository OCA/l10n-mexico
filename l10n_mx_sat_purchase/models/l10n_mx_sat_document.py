# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class L10nMxSatDocument(models.Model):
    _inherit = "l10n_mx_sat.document"

    # Same definition as in l10n_mx_sat_vendor_bill so both modules share the column.
    vendor_bill_id = fields.Many2one(
        comodel_name="account.move",
        string="Vendor bill",
        readonly=True,
        copy=False,
    )

    @api.depends("series", "folio_number", "issuer_name", "total", "currency_code")
    def _compute_display_name(self):
        res = super()._compute_display_name()
        # Folio, issuer and total tell more than the UUID when picking a CFDI.
        for document in self.filtered(
            lambda d: d.document_kind == "cfdi" and d.has_xml
        ):
            folio = "-".join(filter(None, [document.series, document.folio_number]))
            amount = f"{document.total:,.2f} {document.currency_code or ''}".strip()
            document.display_name = " | ".join(
                filter(None, [folio, document.issuer_name, amount, document.uuid])
            )
        return res

    @api.model
    def _get_selectable_domain(self, company, partner=None, currency=None):
        """Domain of the received CFDIs of ``company`` that can still be linked
        to a vendor bill, optionally restricted to ``partner`` and ``currency``."""
        domain = [
            ("company_id", "=", company.id),
            ("document_kind", "=", "cfdi"),
            ("direction", "=", "received"),
            ("voucher_type", "=", "I"),
            ("has_xml", "=", True),
            ("sat_status", "!=", "cancelled"),
            ("vendor_bill_id", "=", False),
        ]
        if company.vat:
            domain.append(("receiver_rfc", "=", company.vat.strip().upper()))
        if partner:
            rfc = (partner.commercial_partner_id.vat or "").strip().upper()
            domain.append(("issuer_rfc", "=", rfc))
        if currency:
            domain.append(("currency_code", "=", currency.name))
        return domain

    def _link_vendor_bill(self, move):
        """Attach the XML to ``move`` and mark the document as billed."""
        self.ensure_one()
        self._sat_write({"vendor_bill_id": move.id})

    def _prepare_vendor_bill_attachment_vals(self):
        """Values of a pending attachment that ``mail.thread.message_post``
        links to the vendor bill once it exists."""
        self.ensure_one()
        return {
            "name": self.attachment_id.name or f"{self.uuid}.xml",
            "raw": self.attachment_id.raw,
            "mimetype": "application/xml",
            "res_model": "mail.compose.message",
        }
