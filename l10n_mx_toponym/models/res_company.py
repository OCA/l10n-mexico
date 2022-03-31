# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_edi_colony = fields.Char(
        compute="_compute_l10n_mx_edi_colony",
        inverse="_inverse_l10n_mx_edi_colony",
        string="Colony",
    )
    l10n_mx_edi_colony_code = fields.Char(
        compute="_compute_l10n_mx_edi_colony_code",
        inverse="_inverse_l10n_mx_edi_colony_code",
        string="Colony Code",
    )
    l10n_mx_edi_locality_id = fields.Many2one(
        comodel_name="l10n_mx_edi.res.locality",
        string="Locality",
        related="partner_id.l10n_mx_edi_locality_id",
        readonly=False,
    )
    country_code = fields.Char(
        related="country_id.code",
        store=True,
    )

    def _compute_l10n_mx_edi_colony(self):
        for company in self.with_context(skip_check_zip=True):
            address_data = company.partner_id.sudo().address_get(adr_pref=["contact"])
            if address_data["contact"]:
                partner = company.partner_id.sudo().browse(address_data["contact"])
                company.l10n_mx_edi_colony = partner.l10n_mx_edi_colony
            else:
                company.l10n_mx_edi_colony = None

    def _compute_l10n_mx_edi_colony_code(self):
        for company in self.with_context(skip_check_zip=True):
            address_data = company.partner_id.sudo().address_get(adr_pref=["contact"])
            if address_data["contact"]:
                partner = company.partner_id.browse(address_data["contact"])
                company.l10n_mx_edi_colony_code = partner.l10n_mx_edi_colony_code

    def _inverse_l10n_mx_edi_colony(self):
        for company in self.with_context(skip_check_zip=True):
            company.partner_id.l10n_mx_edi_colony = company.l10n_mx_edi_colony

    def _inverse_l10n_mx_edi_colony_code(self):
        for company in self.with_context(skip_check_zip=True):
            company.partner_id.l10n_mx_edi_colony_code = company.l10n_mx_edi_colony_code

    @api.onchange("zip_id")
    def _onchange_zip_id(self):
        if self.zip_id:
            self.update(
                {
                    "zip": self.zip_id.name,
                    "city_id": self.zip_id.city_id,
                    "city": self.zip_id.city_id.name,
                    "country_id": self.zip_id.city_id.country_id,
                    "state_id": self.zip_id.city_id.state_id,
                    "l10n_mx_edi_colony": self.zip_id.l10n_mx_edi_colony,
                    "l10n_mx_edi_colony_code": self.zip_id.l10n_mx_edi_colony_code,
                    "l10n_mx_edi_locality_id": self.zip_id.l10n_mx_edi_locality_id,
                }
            )
