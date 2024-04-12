from odoo import models, fields, api


class CFDIServiceTopUp(models.Model):
    _name = "l10n_mx_cfdi.cfdi_service.topup"
    _description = "CFDI Service Top Up"

    topup_date = fields.Datetime(
        string="Fecha de Adquisición", default=fields.Datetime.now()
    )
    stamp_number = fields.Integer(string="Cantidad de Folios", required=True)
    stamp_price = fields.Monetary(
        string="Precio por Folio", required=True, currency_field="currency_id"
    )
    total = fields.Monetary(
        string="Precio Total",
        compute="_compute_total",
        store=True,
        currency_field="currency_id",
    )

    service_id = fields.Many2one(
        "l10n_mx_cfdi.cfdi_service",
        string="Servicio",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contacto",
        required=True,
        readonly=True,
        ondelete="restrict",
        default=lambda self: self.env.user.partner_id,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        required=True,
        readonly=True,
        default=lambda self: self.env.company.currency_id,
    )

    @api.depends("stamp_number", "stamp_price")
    def _compute_total(self):
        for record in self:
            record.total = record.stamp_number * record.stamp_price
