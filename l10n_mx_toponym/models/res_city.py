# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCity(models.Model):
    _inherit = "res.city"

    l10n_mx_edi_code = fields.Char(string="Code MX",)
