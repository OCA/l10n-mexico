from markupsafe import Markup

from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

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
        if self.display_type == "product" and self.l10n_mx_cfid_import_details_required:
            numeros_pedimento = self.l10n_mx_cfdi_pedimento_ids.mapped("number")
            # ensure every space is double as required by facturama
            numeros_pedimento = [
                num.strip().replace(" ", "  ") for num in numeros_pedimento
            ]

            res["NumerosPedimento"] = numeros_pedimento
        return res
