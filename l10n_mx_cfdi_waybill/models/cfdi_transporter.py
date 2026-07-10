from odoo import fields, models


class CFDITransporter(models.Model):
    _name = "l10n_mx_cfdi_waybill.transporter"
    _description = 'Transporter Record used in CFDI of type "Carta Porte"'

    partner_id = fields.Many2one("res.partner", string="Contacto", required=True)
    driving_license = fields.Char(
        string="Licencia de Conducir",
        readonly=False,
        related="partner_id.l10n_mx_cfdi_waybill_driving_license",
    )
    type = fields.Many2one("l10n_mx_catalogs.c_figura_transporte", string="Tipo")
    type_code = fields.Char(related="type.code")

    parte_transporte_ids = fields.Many2many(
        "l10n_mx_catalogs.c_parte_transporte",
        string="Partes de Transporte",
        relation="cfdi_transporter_parte_transporte_rel",
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
