# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from collections import defaultdict

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero

from ..models.purchase_order_line import normalize_text, strip_code_prefix
from ..models.res_company import MATCH_MODES


class L10nMxSatPurchaseInvoiceWizard(models.TransientModel):
    _name = "l10n_mx_sat.purchase.invoice.wizard"
    _inherit = "l10n_mx_sat.document.selector.mixin"
    _description = "Create the vendor bill of purchase orders from a SAT CFDI"

    purchase_order_ids = fields.Many2many(
        comodel_name="purchase.order",
        string="Purchase Orders",
        required=True,
    )
    partner_id = fields.Many2one(compute="_compute_from_orders")
    commercial_partner_id = fields.Many2one(
        comodel_name="res.partner", compute="_compute_from_orders"
    )
    company_id = fields.Many2one(compute="_compute_from_orders")
    currency_id = fields.Many2one(compute="_compute_from_orders")
    amount_total = fields.Monetary(
        string="Orders Total", compute="_compute_from_orders"
    )
    match_mode = fields.Selection(
        selection=MATCH_MODES,
        string="Match",
        compute="_compute_match_mode",
        store=True,
        readonly=False,
        required=True,
        precompute=True,
    )
    available_purchase_line_ids = fields.Many2many(
        comodel_name="purchase.order.line",
        compute="_compute_available_purchase_line_ids",
        help="Lines of the selected orders that still have a quantity to bill.",
    )
    concept_ids = fields.One2many(
        comodel_name="l10n_mx_sat.purchase.invoice.wizard.concept",
        inverse_name="wizard_id",
        string="CFDI Concepts",
        compute="_compute_concept_ids",
        store=True,
        readonly=False,
    )
    concept_document_id = fields.Many2one(
        comodel_name="l10n_mx_sat.document",
        compute="_compute_concept_ids",
        store=True,
        help="CFDI the concepts were built from.",
    )
    cfdi_amount_untaxed = fields.Monetary(
        string="CFDI Subtotal",
        compute="_compute_amounts",
        help="Subtotal of the CFDI after discounts.",
    )
    mapped_amount_untaxed = fields.Monetary(
        string="Amount to Bill",
        compute="_compute_amounts",
        help="Untaxed amount of the concepts with the quantities to bill.",
    )
    total_mismatch = fields.Boolean(compute="_compute_amounts")

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if defaults.get("purchase_order_ids") and not defaults.get(
            "l10n_mx_sat_document_id"
        ):
            wizard = self.new({"purchase_order_ids": defaults["purchase_order_ids"]})
            defaults["l10n_mx_sat_document_id"] = wizard._find_default_document().id
        return defaults

    @api.depends("purchase_order_ids")
    def _compute_from_orders(self):
        for wizard in self:
            orders = wizard.purchase_order_ids
            wizard.partner_id = orders[:1].partner_id
            wizard.commercial_partner_id = orders[:1].partner_id.commercial_partner_id
            wizard.company_id = orders[:1].company_id
            wizard.currency_id = orders[:1].currency_id
            wizard.amount_total = sum(orders.mapped("amount_total"))

    @api.depends("purchase_order_ids")
    def _compute_match_mode(self):
        # Adding or removing orders keeps the mode chosen by the user
        for wizard in self.filtered(lambda wizard: not wizard.match_mode):
            order = wizard.purchase_order_ids[:1]
            partner = order.partner_id.commercial_partner_id.with_company(
                order.company_id
            )
            wizard.match_mode = (
                partner.l10n_mx_sat_purchase_match_mode
                or order.company_id.l10n_mx_sat_purchase_match_mode
                or "document"
            )

    @api.depends(
        "purchase_order_ids.state", "purchase_order_ids.order_line.qty_to_invoice"
    )
    def _compute_available_purchase_line_ids(self):
        for wizard in self:
            wizard.available_purchase_line_ids = wizard._get_available_lines()

    def _get_available_lines(self):
        """Lines of the orders that can still be billed, read from the database
        (the cache of the computed field may be stale after billing)."""
        self.ensure_one()
        # The orders are real records even on a new wizard: use their lines
        lines = self.purchase_order_ids._origin.order_line
        lines.invalidate_recordset(["qty_to_invoice"])
        return lines.filtered(
            lambda line: line.order_id.state == "purchase"
            and not line.display_type
            and float_compare(
                line.qty_to_invoice, 0, precision_rounding=line.product_uom_id.rounding
            )
            > 0
        )

    @api.depends("l10n_mx_sat_document_id", "available_purchase_line_ids")
    def _compute_concept_ids(self):
        for wizard in self:
            document = wizard.l10n_mx_sat_document_id
            if document != wizard.concept_document_id:
                commands = [Command.clear()]
                if document:
                    commands += [
                        Command.create(vals) for vals in document._get_cfdi_concepts()
                    ]
                wizard.concept_ids = commands
                wizard.concept_document_id = document
            # Keep the mapping done by the user: only propose the pending concepts
            wizard._propose_purchase_lines(
                wizard.concept_ids.filtered(lambda c: not c.purchase_line_id)
            )

    @api.depends(
        "l10n_mx_sat_document_id",
        "match_mode",
        "amount_total",
        "concept_ids.purchase_line_id",
        "concept_ids.qty_to_invoice",
    )
    def _compute_amounts(self):
        for wizard in self:
            document = wizard.l10n_mx_sat_document_id
            wizard.cfdi_amount_untaxed = 0.0
            wizard.mapped_amount_untaxed = 0.0
            wizard.total_mismatch = False
            if not document:
                continue
            amounts = document._get_cfdi_amounts()
            wizard.cfdi_amount_untaxed = amounts["subtotal"] - amounts["discount"]
            wizard.mapped_amount_untaxed = sum(
                concept._get_amount_untaxed() for concept in wizard.concept_ids
            )
            if wizard.match_mode == "document":
                wizard.total_mismatch = bool(
                    wizard.currency_id.compare_amounts(
                        document.total, wizard.amount_total
                    )
                )
                continue
            wizard.total_mismatch = bool(
                wizard.currency_id.compare_amounts(
                    wizard.mapped_amount_untaxed, wizard.cfdi_amount_untaxed
                )
                if wizard.currency_id
                else float_compare(
                    wizard.mapped_amount_untaxed,
                    wizard.cfdi_amount_untaxed,
                    precision_digits=2,
                )
            )

    @api.constrains("purchase_order_ids")
    def _check_purchase_order_ids(self):
        for wizard in self:
            orders = wizard.purchase_order_ids
            if (
                len(orders.partner_id.commercial_partner_id) > 1
                or len(orders.company_id) > 1
            ):
                raise ValidationError(
                    self.env._(
                        "The purchase orders must belong to the same vendor and company"
                    )
                )
            if len(orders.currency_id) > 1:
                raise ValidationError(
                    self.env._("The purchase orders must use the same currency.")
                )

    def _find_default_document(self):
        """Return the only CFDI whose total is the orders total or, failing
        that, the only one within the tolerance of the company."""
        self.ensure_one()
        Document = self.env["l10n_mx_sat.document"]
        if not self.company_id:
            return Document
        domain = Document._get_selectable_domain(
            self.company_id, self.partner_id, self.currency_id
        )
        tolerances = (
            self.currency_id.rounding / 2,
            self.company_id.l10n_mx_sat_purchase_total_tolerance,
        )
        for tolerance in tolerances:
            documents = Document.search(
                domain
                + [
                    ("total", ">=", self.amount_total - tolerance),
                    ("total", "<=", self.amount_total + tolerance),
                ],
                limit=2,
            )
            if documents:
                return documents if len(documents) == 1 else Document
        return Document

    # ------------------------------------------------------------------
    # Mapping proposal
    # ------------------------------------------------------------------

    def _get_sorted_available_lines(self):
        """Available lines, oldest order first, so ties go to the oldest pending."""
        self.ensure_one()
        return self.available_purchase_line_ids.sorted(
            key=lambda line: (
                line.order_id.date_approve or line.order_id.date_order,
                line.order_id.id,
                line.sequence,
                line.id,
            )
        )

    def _propose_purchase_lines(self, concepts):
        """Set ``purchase_line_id`` of ``concepts`` with the best matching line.

        For each concept, in the order of the CFDI, the candidates are searched
        by vendor/internal code, then by description and finally by a unique
        price; the first candidate whose pending quantity is not already taken
        by another concept wins. When it cannot take the whole concept and
        there are more candidates, the concept is split and the rest goes to
        the next one.
        """
        self.ensure_one()
        lines = self._get_sorted_available_lines()
        if not lines or not concepts:
            return
        remaining = {line: line.qty_to_invoice for line in lines}
        for concept in self.concept_ids - concepts:
            if concept.purchase_line_id in remaining:
                remaining[concept.purchase_line_id] -= concept.qty_to_invoice
        queue = list(concepts)
        while queue:
            concept = queue.pop(0)
            candidates = [
                line
                for line in concept._find_candidate_lines(lines)
                if float_compare(
                    remaining[line], 0, precision_rounding=line.product_uom_id.rounding
                )
                > 0
            ]
            if not candidates:
                continue
            line = candidates[0]
            quantity = concept._get_invoice_quantity_and_price(line)[0]
            if candidates[1:] and (
                float_compare(
                    quantity,
                    remaining[line],
                    precision_rounding=line.product_uom_id.rounding,
                )
                > 0
            ):
                queue.insert(0, concept._split(remaining[line] / quantity))
                quantity = remaining[line]
            concept.purchase_line_id = line
            remaining[line] -= quantity

    # ------------------------------------------------------------------
    # Bill creation
    # ------------------------------------------------------------------

    def action_create_invoice(self):
        self.ensure_one()
        rejection = self._l10n_mx_sat_check_document()
        if rejection:
            return self._l10n_mx_sat_rejection_action(rejection)
        orders = self.purchase_order_ids
        if orders.filtered(lambda o: o.state != "purchase"):
            raise UserError(self.env._("Only confirmed purchase orders can be billed."))
        if self.match_mode == "document":
            return self._create_invoice_from_orders()
        if not self.concept_ids:
            raise UserError(
                self.env._(
                    "The CFDI %s has no concepts to bill.",
                    self.l10n_mx_sat_document_id.uuid,
                )
            )
        self._check_concepts()
        if self.company_id.l10n_mx_sat_purchase_learn_vendor_code:
            self._learn_vendor_codes()
        document = self.l10n_mx_sat_document_id
        move = self._create_vendor_bill()
        attachment = self.env["ir.attachment"].create(
            document._prepare_vendor_bill_attachment_vals()
        )
        self._attach_cfdi(move, attachment)
        document._link_vendor_bill(move)
        self._check_bill_total(move)
        return (
            self.concept_ids.purchase_line_id.order_id or orders
        ).action_view_invoice(move)

    def _create_invoice_from_orders(self):
        """Bill everything pending in the orders, with the XML of the CFDI."""
        orders = self.purchase_order_ids
        document = self.l10n_mx_sat_document_id
        if len(orders.partner_id) > 1:
            # Odoo bills each vendor contact apart and takes an XML for one bill
            raise UserError(
                self.env._(
                    "The purchase orders belong to different contacts of the "
                    "vendor: match them by lines to bill them together."
                )
            )
        attachment = self.env["ir.attachment"].create(
            document._prepare_vendor_bill_attachment_vals()
        )
        invoices_before = orders.invoice_ids
        action = orders.action_create_invoice(attachment_ids=attachment.ids)
        document._link_vendor_bill(orders.invoice_ids - invoices_before)
        return action

    def _learn_vendor_codes(self):
        """Keep the code the vendor gives to the products mapped by hand, so
        the next CFDI with that code is mapped alone."""
        vendor = self.commercial_partner_id
        for concept in self.concept_ids.filtered("no_identificacion"):
            line = concept.purchase_line_id
            code = concept.no_identificacion.strip()
            if not line.product_id or code.upper() in (
                line._l10n_mx_sat_get_vendor_codes(vendor)
                | {(line.product_id.default_code or "").strip().upper()}
            ):
                continue
            # Buyers only read vendor pricelists; here they just add the code
            seller = (
                line._l10n_mx_sat_get_vendor_infos(vendor)
                .filtered(lambda seller: not seller.product_code)[:1]
                .sudo()
            )
            if seller:
                seller.product_code = code
            else:
                self.env["product.supplierinfo"].sudo().create(
                    {
                        "partner_id": vendor.id,
                        "product_tmpl_id": line.product_id.product_tmpl_id.id,
                        "product_id": line.product_id.id,
                        "product_code": code,
                        "price": line.price_unit,
                        "currency_id": line.currency_id.id,
                        "company_id": self.company_id.id,
                    }
                )

    def _check_concepts(self):
        """Raise when the concepts cannot be billed as they are mapped. The
        ones without purchase order line are billed without one."""
        self.ensure_one()
        quantities = defaultdict(float)
        for concept in self.concept_ids:
            line = concept.purchase_line_id
            rounding = (
                line.product_uom_id or concept.product_id.uom_id
            ).rounding or 0.01
            if (
                float_compare(concept.qty_to_invoice, 0, precision_rounding=rounding)
                <= 0
            ):
                raise UserError(
                    self.env._(
                        "The quantity to bill of the concept '%s' must be positive.",
                        concept.description,
                    )
                )
            if line:
                quantities[line] += concept.qty_to_invoice
        available = self._get_available_lines()
        for line, quantity in quantities.items():
            if line not in available:
                raise UserError(
                    self.env._(
                        "The purchase order line '%s' has nothing left to bill.",
                        line.display_name,
                    )
                )
            if (
                float_compare(
                    quantity,
                    line.qty_to_invoice,
                    precision_rounding=line.product_uom_id.rounding,
                )
                > 0
            ):
                raise UserError(
                    self.env._(
                        "The quantity to bill of '%(line)s' (%(quantity)s %(uom)s) "
                        "exceeds its pending quantity (%(pending)s %(uom)s).",
                        line=line.display_name,
                        quantity=quantity,
                        pending=line.qty_to_invoice,
                        uom=line.product_uom_id.name,
                    )
                )

    def _prepare_vendor_bill_vals(self):
        self.ensure_one()
        document = self.l10n_mx_sat_document_id
        orders = self.concept_ids.purchase_line_id.order_id or self.purchase_order_ids
        vals = orders[:1].with_company(self.company_id)._prepare_invoice()
        vals.update(
            {
                "invoice_origin": ", ".join(orders.mapped("name")),
                "ref": "-".join(filter(None, [document.series, document.folio_number]))
                or document.uuid,
                "invoice_date": document.issue_date and document.issue_date.date(),
                "invoice_line_ids": [
                    Command.create(concept._prepare_invoice_line_vals(sequence))
                    for sequence, concept in enumerate(self.concept_ids, start=1)
                ],
            }
        )
        uuid_field = self.env["account.move"]._fields.get("l10n_mx_cfdi_uuid")
        if uuid_field and not uuid_field.compute:
            # Plain field of l10n_mx_sat_vendor_bill; l10n_mx_edi computes its own
            vals["l10n_mx_cfdi_uuid"] = document.uuid
        return vals

    def _create_vendor_bill(self):
        self.ensure_one()
        vals = self._prepare_vendor_bill_vals()
        return (
            self.env["account.move"]
            .with_context(default_move_type="in_invoice")
            .with_company(self.company_id)
            .create(vals)
        )

    def _attach_cfdi(self, move, attachment):
        """Link the XML to the bill the same way ``purchase`` does on upload,
        so the CFDI decoders of the localization process it."""
        move.with_context(skip_is_manually_modified=True)._extend_with_attachments(
            move._to_files_data(attachment), new=True
        )
        move.message_post(attachment_ids=attachment.ids)
        attachment.write({"res_model": "account.move", "res_id": move.id})

    def _check_bill_total(self, move):
        """Warn in the chatter when the bill total differs from the CFDI total."""
        document = self.l10n_mx_sat_document_id
        if not move.currency_id.compare_amounts(move.amount_total, document.total):
            return False
        move.message_post(
            body=self.env._(
                "The total of the bill (%(bill)s) differs from the total of the "
                "CFDI %(uuid)s (%(cfdi)s). Review the quantities and taxes before "
                "posting it.",
                bill=move.currency_id.format(move.amount_total),
                uuid=document.uuid,
                cfdi=move.currency_id.format(document.total),
            )
        )
        return True


class L10nMxSatPurchaseInvoiceWizardConcept(models.TransientModel):
    _name = "l10n_mx_sat.purchase.invoice.wizard.concept"
    _description = "Concept of a SAT CFDI mapped to a purchase order line"
    _order = "sequence, id"

    wizard_id = fields.Many2one(
        comodel_name="l10n_mx_sat.purchase.invoice.wizard",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=1)
    no_identificacion = fields.Char(string="Vendor Code")
    description = fields.Char()
    product_service_code = fields.Char(string="SAT Product Code")
    quantity = fields.Float(string="CFDI Quantity", digits="Product Unit")
    unit_code = fields.Char(string="SAT Unit")
    price_unit = fields.Float(string="CFDI Unit Price", digits="Product Price")
    amount = fields.Float(string="CFDI Amount")
    discount_amount = fields.Float(string="CFDI Discount")
    tax_amount = fields.Float(string="CFDI Taxes")
    tax_summary = fields.Char(string="Taxes")
    purchase_line_id = fields.Many2one(
        comodel_name="purchase.order.line", string="Purchase Order Line"
    )
    purchase_order_id = fields.Many2one(
        related="purchase_line_id.order_id", string="Purchase Order"
    )
    purchase_uom_id = fields.Many2one(
        related="purchase_line_id.product_uom_id", string="Order Unit"
    )
    purchase_qty_pending = fields.Float(
        related="purchase_line_id.qty_to_invoice", string="Pending Quantity"
    )
    purchase_price_unit = fields.Float(
        related="purchase_line_id.price_unit", string="Order Unit Price"
    )
    price_mismatch = fields.Boolean(compute="_compute_price_mismatch")
    product_id = fields.Many2one(
        comodel_name="product.product",
        compute="_compute_product_id",
        store=True,
        readonly=False,
        help="Product of the purchase order line, or the product to bill when "
        "the concept has no line.",
    )
    qty_to_invoice = fields.Float(
        string="Quantity to Bill",
        digits="Product Unit",
        compute="_compute_qty_to_invoice",
        store=True,
        readonly=False,
        help="Quantity of the CFDI in the unit of the purchase order line.",
    )

    @api.depends("purchase_line_id")
    def _compute_product_id(self):
        for concept in self.filtered("purchase_line_id"):
            concept.product_id = concept.purchase_line_id.product_id

    @api.depends("purchase_line_id", "price_unit", "quantity", "unit_code")
    def _compute_price_mismatch(self):
        """The price of the CFDI differs from the one of the order beyond the
        tolerance of the company."""
        for concept in self:
            line = concept.purchase_line_id
            tolerance = (
                concept.wizard_id.company_id.l10n_mx_sat_purchase_price_tolerance / 100
            )
            price_unit = concept._get_invoice_quantity_and_price()[1]
            concept.price_mismatch = bool(line) and (
                abs(price_unit - line.price_unit)
                > abs(line.price_unit) * tolerance + 1e-6
            )

    @api.depends("purchase_line_id", "quantity", "unit_code")
    def _compute_qty_to_invoice(self):
        for concept in self:
            concept.qty_to_invoice = concept._get_invoice_quantity_and_price()[0]

    def _get_uom_from_unit_code(self):
        """Unit of measure matching the SAT ``ClaveUnidad`` of the concept, if
        the UNSPSC codes of ``product_unspsc`` are installed."""
        self.ensure_one()
        Uom = self.env["uom.uom"]
        if not self.unit_code or "unspsc_code_id" not in Uom._fields:
            return Uom
        return Uom.search([("unspsc_code_id.code", "=", self.unit_code)], limit=1)

    def _get_invoice_quantity_and_price(self, line=None):
        """Quantity and unit price of the concept in the unit of ``line`` (the
        mapped purchase line by default). The CFDI values are kept when the
        SAT unit is unknown or not convertible."""
        self.ensure_one()
        line = line or self.purchase_line_id
        quantity, price_unit = self.quantity, self.price_unit
        uom = self._get_uom_from_unit_code()
        line_uom = line.product_uom_id
        if uom and line_uom and uom != line_uom and uom._has_common_reference(line_uom):
            converted = uom._compute_quantity(quantity, line_uom, round=False)
            if not float_is_zero(converted, precision_rounding=line_uom.rounding):
                price_unit = price_unit * quantity / converted
                quantity = converted
        return quantity, price_unit

    def _get_discount_percent(self):
        self.ensure_one()
        if not self.amount or not self.discount_amount:
            return 0.0
        return self.discount_amount / self.amount * 100

    def _get_amount_untaxed(self):
        """Untaxed amount of the concept with the quantity to bill."""
        self.ensure_one()
        price_unit = self._get_invoice_quantity_and_price()[1]
        return (
            self.qty_to_invoice * price_unit * (1 - self._get_discount_percent() / 100)
        )

    def _find_candidate_lines(self, lines):
        """Purchase lines matching the concept, best criterion first.

        1. ``NoIdentificacion`` equal to the internal reference of the product
           or to the vendor code of the product for this vendor.
        2. Description equal (normalized) to the line description, the product
           name or the vendor product name.
        3. A single available line with the same unit price.

        When several lines match by code or description (same product ordered
        several times), the ones with the same unit price are preferred.
        """
        self.ensure_one()
        wizard = self.wizard_id
        vendor = wizard.commercial_partner_id
        currency = wizard.currency_id
        price_matches = lines.filtered(
            lambda line: not currency.compare_amounts(line.price_unit, self.price_unit)
        )
        code = (self.no_identificacion or "").strip().upper()
        if code:
            matches = lines.filtered(
                lambda line: (line.product_id.default_code or "").strip().upper()
                == code
                or code in line._l10n_mx_sat_get_vendor_codes(vendor)
            )
            if matches:
                return (matches & price_matches) or matches
        description = normalize_text(strip_code_prefix(self.description))
        if description:
            matches = lines.filtered(
                lambda line: description in line._l10n_mx_sat_get_descriptions(vendor)
            )
            if matches:
                return (matches & price_matches) or matches
        if len(price_matches) == 1:
            return price_matches
        return lines.browse()

    def _prepare_invoice_line_vals(self, sequence):
        """Values of the ``account.move.line`` billing this concept."""
        self.ensure_one()
        line = self.purchase_line_id
        price_unit = self._get_invoice_quantity_and_price()[1]
        if line:
            vals = line._prepare_account_move_line()
        else:
            # No purchase order line: billed without one, the product is optional
            vals = {
                "display_type": "product",
                "product_id": self.product_id.id,
                "name": self.description,
            }
        vals.update({"sequence": sequence, "quantity": self.qty_to_invoice})
        company = self.wizard_id.company_id
        if not line or company.l10n_mx_sat_purchase_price_source == "cfdi":
            vals.update(
                {"price_unit": price_unit, "discount": self._get_discount_percent()}
            )
        return vals

    def _split(self, ratio):
        """Keep ``ratio`` of the concept and return a new one with the rest,
        to bill it in another purchase order line."""
        self.ensure_one()
        wizard = self.wizard_id
        split_fields = ("quantity", "amount", "discount_amount", "tax_amount")
        vals = {
            name: self[name]
            for name in (
                "sequence",
                "no_identificacion",
                "description",
                "product_service_code",
                "unit_code",
                "price_unit",
                "tax_summary",
            )
        }
        for name in split_fields:
            # Rounded so both parts still add up to the concept of the CFDI
            vals[name] = round(self[name] * (1 - ratio), 6)
            self[name] -= vals[name]
        concepts = wizard.concept_ids
        wizard.concept_ids = [Command.create(vals)]
        return wizard.concept_ids - concepts

    def action_split(self):
        """Move what is not billed in this purchase order line to a new line
        of the same concept."""
        self.ensure_one()
        quantity = self._get_invoice_quantity_and_price()[0]
        rounding = (self.purchase_uom_id or self.product_id.uom_id).rounding or 0.01
        if (
            float_compare(self.qty_to_invoice, 0, precision_rounding=rounding) <= 0
            or float_compare(self.qty_to_invoice, quantity, precision_rounding=rounding)
            >= 0
        ):
            raise UserError(
                self.env._(
                    "Lower the quantity to bill of '%s' to what this purchase "
                    "order line takes: the rest goes to a new line of the concept.",
                    self.description,
                )
            )
        self._split(self.qty_to_invoice / quantity)
        wizard = self.wizard_id
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Bill from SAT CFDI"),
            "res_model": wizard._name,
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }
