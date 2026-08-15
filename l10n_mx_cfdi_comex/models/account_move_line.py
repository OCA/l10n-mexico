import re

from markupsafe import Markup

from odoo import api, fields, models

# SAT cfdv40 NumeroPedimento: length 21, double spaces between groups.
_SAT_PEDIMENTO_RE = re.compile(r"^(\d{2})\s+(\d{2})\s+(\d{4})\s+(\d{7})$")
_FACTURAMA_DESCRIPTION_MAX = 1000


def _sat_pedimento_number(number):
    """Normalize a pedimento to SAT ``AA  BB  CCCC  DDDDDDD`` (21 chars)."""
    if not number:
        return None
    text = str(number).strip()
    match = _SAT_PEDIMENTO_RE.match(text)
    if not match:
        return text or None
    return "  ".join(match.groups())


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_mx_cfdi_cce_no_identificacion = fields.Char(
        string="No identificación CCE",
        help=(
            "CCE NoIdentificacion. Defaults to the product Internal Reference "
            "when empty."
        ),
    )
    l10n_mx_cfdi_cce_valor_dolares = fields.Float(
        string="Valor dólares",
        digits=(16, 2),
        help="Total value in USD for this line (CCE ValorDolares).",
    )
    l10n_mx_cfdi_cce_cantidad_aduana = fields.Float(
        string="Cantidad aduana",
        digits=(16, 3),
        help="Customs quantity (CCE CantidadAduana). Defaults to invoice quantity.",
    )
    l10n_mx_cfdi_cce_unidad_aduana = fields.Char(
        string="Unidad aduana",
        size=2,
        default="01",
        help="SAT c_UnidadAduana code (e.g. 01 = Kg, 06 = Piece).",
    )
    l10n_mx_cfdi_cce_valor_unitario_aduana = fields.Float(
        string="Valor unitario aduana",
        digits=(16, 6),
        help="Unit customs value in USD (CCE ValorUnitarioAduana).",
    )

    l10n_mx_cfdi_pedimento_ids = fields.Many2many(
        comodel_name="l10n_mx_cfdi.pedimento",
        string="Pedimentos",
        help=(
            "Pedimentos relacionados con esta línea de factura para "
            "cumplimiento de regulaciones mexicanas."
        ),
        compute="_compute_l10n_mx_cfdi_pedimento_ids",
    )

    l10n_mx_cfid_import_details = fields.Text(
        string="Import details",
        compute="_compute_l10n_mx_cfid_import_details",
        help="Import details for Mexican regulations compliance",
    )
    l10n_mx_cfid_import_details_required = fields.Boolean(
        string="Import details required",
        compute="_compute_l10n_mx_cfid_import_details_required",
        default=False,
    )

    @api.depends("sale_line_ids")
    def _compute_l10n_mx_cfdi_pedimento_ids(self):
        for record in self:
            lot_ids = record.sale_line_ids.move_ids.lot_ids
            if lot_ids:
                record.l10n_mx_cfdi_pedimento_ids = lot_ids.l10n_mx_cfdi_pedimento_id
            else:
                record.l10n_mx_cfdi_pedimento_ids = False

    @api.depends("l10n_mx_cfdi_pedimento_ids")
    def _compute_l10n_mx_cfid_import_details(self):
        """Build import details for Mexican foreign trade invoice lines."""

        for record in self:
            if record.l10n_mx_cfid_import_details_required:
                fraccion = record.product_id.product_tmpl_id.l10n_mx_cfdi_tariff_code

                details = f"\n\nFracción: {fraccion.code} - {fraccion.name}\n"
                for pedimento in record.l10n_mx_cfdi_pedimento_ids:
                    aduana = pedimento.customs_id
                    details += (
                        f"Pedimento: {pedimento.number}, Fecha: {pedimento.date}\n"
                        f"Aduana: {aduana.code} {aduana.name}\n"
                    )
                record.l10n_mx_cfid_import_details = details
            else:
                record.l10n_mx_cfid_import_details = False

    @api.depends("company_id.country_id", "l10n_mx_cfdi_pedimento_ids")
    def _compute_l10n_mx_cfid_import_details_required(self):
        """Require import details for MX companies when pedimentos are linked."""

        for record in self:
            record.l10n_mx_cfid_import_details_required = (
                record.company_id.country_id.code == "MX"
                and record.l10n_mx_cfdi_pedimento_ids
            )

    @api.model
    def create(self, vals):
        res = super().create(vals)
        for rec in res:
            if (
                rec.display_type == "product"
                and rec.l10n_mx_cfid_import_details_required
            ):
                rec.name += Markup(rec.l10n_mx_cfid_import_details)
        return res

    def _gater_cfdi_item_data(self):
        res = super()._gater_cfdi_item_data()
        if self.display_type != "product":
            return res

        # Import narrative is appended to line.name for the printed invoice, but
        # Facturama/SAT Description rejects control-heavy / overlong text
        # (often as opaque "Error no clasificado"). Keep NumerosPedimento only.
        details = self.l10n_mx_cfid_import_details
        description = str(res.get("Description") or "")
        if details:
            details_text = str(details)
            if details_text and details_text in description:
                description = description.replace(details_text, "")
        description = " ".join(description.split()).strip()
        if description:
            res["Description"] = description[:_FACTURAMA_DESCRIPTION_MAX]

        if not self.l10n_mx_cfid_import_details_required:
            return res

        # CFDI40195: NumeroPedimento must not appear with ComercioExterior.
        if self.move_id.l10n_mx_cfdi_cce_enabled:
            return res

        numeros_pedimento = [
            pedimento
            for pedimento in (
                _sat_pedimento_number(num)
                for num in self.l10n_mx_cfdi_pedimento_ids.mapped("number")
            )
            if pedimento
        ]
        if numeros_pedimento:
            res["NumerosPedimento"] = numeros_pedimento
        return res
