# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_mx_edi_locality_id = fields.Many2one(
        comodel_name="l10n_mx_edi.res.locality",
        string="Locality",
        compute="_compute_l10n_mx_edi_locality_id",
        store=True,
        readonly=False,
    )
    l10n_mx_edi_colony = fields.Char(
        string="Colony",
        compute="_compute_l10n_mx_edi_colony",
        store=True,
        readonly=False,
    )
    l10n_mx_edi_colony_code = fields.Char(
        string="Colony Code",
        compute="_compute_l10n_mx_edi_colony_code",
        store=True,
        readonly=False,
    )

    @api.depends("zip_id")
    def _compute_l10n_mx_edi_locality_id(self):
        if hasattr(super(), "_compute_l10n_mx_edi_locality_id"):
            return super()._compute_l10n_mx_edi_locality_id()  # pragma: no cover
        for record in self:
            if record.zip_id:
                record.l10n_mx_edi_locality_id = record.zip_id.l10n_mx_edi_locality_id
            elif not record.country_enforce_cities:
                record.l10n_mx_edi_locality_id = False

    @api.depends("zip_id")
    def _compute_l10n_mx_edi_colony(self):
        if hasattr(super(), "_compute_l10n_mx_edi_colony"):
            return super()._compute_l10n_mx_edi_colony()  # pragma: no cover
        for record in self:
            if record.zip_id:
                record.l10n_mx_edi_colony = record.zip_id.l10n_mx_edi_colony
            elif not record.country_enforce_cities:
                record.l10n_mx_edi_colony = False

    @api.depends("zip_id")
    def _compute_l10n_mx_edi_colony_code(self):
        if hasattr(super(), "_compute_l10n_mx_edi_colony_code"):
            return super()._compute_l10n_mx_edi_colony_code()  # pragma: no cover
        for record in self:
            if record.zip_id:
                record.l10n_mx_edi_colony_code = record.zip_id.l10n_mx_edi_colony_code
            elif not record.country_enforce_cities:
                record.l10n_mx_edi_colony_code = False

    @api.model
    def _address_fields(self):
        return super()._address_fields() + [
            "l10n_mx_edi_locality_id",
            "l10n_mx_edi_colony",
            "l10n_mx_edi_colony_code",
        ]
