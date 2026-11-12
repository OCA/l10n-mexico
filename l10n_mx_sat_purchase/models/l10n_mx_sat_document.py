# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging

from lxml import etree

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CFDI_TAX_CODE_TO_NAME = {"001": "ISR", "002": "IVA", "003": "IEPS"}


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
        company_rfc = (company.vat or "").strip().upper()
        if not company_rfc:
            # The receiver of the CFDI cannot be checked without the company RFC
            return [("id", "in", [])]
        domain = [
            ("company_id", "=", company.id),
            ("receiver_rfc", "=", company_rfc),
            ("document_kind", "=", "cfdi"),
            ("direction", "=", "received"),
            ("voucher_type", "=", "I"),
            ("has_xml", "=", True),
            ("sat_status", "!=", "cancelled"),
            ("vendor_bill_id", "=", False),
        ]
        if partner:
            rfc = (partner.commercial_partner_id.vat or "").strip().upper()
            domain.append(("issuer_rfc", "=", rfc))
        if currency:
            domain.append(("currency_code", "=", currency.name))
        return domain

    def action_l10n_mx_sat_match_purchase_orders(self):
        """Map the concepts of the CFDI to the purchase orders of its issuer
        that are pending to bill."""
        self.ensure_one()
        orders = self.env["purchase.order"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("state", "=", "purchase"),
                ("invoice_status", "=", "to invoice"),
                ("partner_id.commercial_partner_id.vat", "=", self.issuer_rfc),
                ("currency_id.name", "=", self.currency_code),
            ]
        )
        if not orders:
            raise UserError(
                self.env._(
                    "There is no purchase order of %(vendor)s pending to bill "
                    "in %(currency)s.",
                    vendor=self.issuer_name or self.issuer_rfc,
                    currency=self.currency_code,
                )
            )
        action = orders.action_l10n_mx_sat_select_document()
        action["context"].update(
            default_l10n_mx_sat_document_id=self.id, default_match_mode="line"
        )
        return action

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

    def _get_cfdi_tree(self):
        """Root element of the CFDI XML stored in ``attachment_id``, or None."""
        self.ensure_one()
        raw = self.attachment_id.with_context(bin_size=False).raw
        if not raw:
            return None
        try:
            return etree.fromstring(raw)
        except etree.XMLSyntaxError:
            _logger.warning(
                "The XML of the SAT document %s cannot be parsed", self.uuid
            )
            return None

    def _get_cfdi_amounts(self):
        """Header amounts of the CFDI: ``subtotal``, ``discount`` and ``total``."""
        tree = self._get_cfdi_tree()
        if tree is None:
            return {"subtotal": 0.0, "discount": 0.0, "total": self.total}
        return {
            "subtotal": _to_float(tree.get("SubTotal")),
            "discount": _to_float(tree.get("Descuento")),
            "total": _to_float(tree.get("Total"), self.total),
        }

    def _get_cfdi_concepts(self):
        """Concepts of the CFDI as a list of dicts, in the order of the XML.

        Each dict has the attributes of ``cfdi:Concepto`` (``no_identificacion``,
        ``description``, ``product_service_code``, ``quantity``, ``unit_code``,
        ``price_unit``, ``amount``, ``discount_amount``) plus the taxes of the
        concept: ``tax_amount`` (transferred minus withheld) and ``tax_summary``
        (human readable rates).
        """
        tree = self._get_cfdi_tree()
        if tree is None:
            return []
        concepts = []
        for sequence, node in enumerate(
            tree.findall("{*}Conceptos/{*}Concepto"), start=1
        ):
            tax_amount = 0.0
            summary = []
            for kind, path in (
                ("transferred", "{*}Impuestos/{*}Traslados/{*}Traslado"),
                ("withheld", "{*}Impuestos/{*}Retenciones/{*}Retencion"),
            ):
                for tax_node in node.findall(path):
                    amount = _to_float(tax_node.get("Importe"))
                    tax_amount += amount if kind == "transferred" else -amount
                    summary.append(self._format_cfdi_tax(tax_node, kind == "withheld"))
            concepts.append(
                {
                    "sequence": sequence,
                    "no_identificacion": node.get("NoIdentificacion") or False,
                    "description": node.get("Descripcion") or False,
                    "product_service_code": node.get("ClaveProdServ") or False,
                    "quantity": _to_float(node.get("Cantidad"), 1.0),
                    "unit_code": node.get("ClaveUnidad") or False,
                    "price_unit": _to_float(node.get("ValorUnitario")),
                    "amount": _to_float(node.get("Importe")),
                    "discount_amount": _to_float(node.get("Descuento")),
                    "tax_amount": tax_amount,
                    "tax_summary": ", ".join(summary),
                }
            )
        return concepts

    @api.model
    def _format_cfdi_tax(self, tax_node, withheld=False):
        name = CFDI_TAX_CODE_TO_NAME.get(
            tax_node.get("Impuesto"), tax_node.get("Impuesto")
        )
        if tax_node.get("TipoFactor") == "Exento":
            rate = self.env._("Exempt")
        else:
            rate = f"{_to_float(tax_node.get('TasaOCuota')) * 100:g}%"
        return f"{self.env._('Ret.') + ' ' if withheld else ''}{name} {rate}"
