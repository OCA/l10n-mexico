# Copyright (C) 2024 Alexis López Zubieta (https://augetec.com).
# License GPL-3.0 or later (http://www.gnu.org/licenses/gpl).

import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10nMxCFDIPedimento(models.Model):
    _name = "l10n_mx_cfdi.pedimento"
    _description = "Pedimento"
    _rec_name = "name"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Nombre",
        compute="_compute_name",
        store=True,
    )

    number = fields.Char(
        string="Número de Pedimento",
        required=True,
    )

    customs_id = fields.Many2one(
        "l10n_mx_catalogs.c_aduana",
        string="Aduana",
        required=True,
    )

    date = fields.Date(
        string="Fecha",
        required=True,
        default=fields.Date.context_today,
    )

    lot_ids = fields.One2many(
        "stock.lot",
        "l10n_mx_cfdi_pedimento_id",
        string="Lotes",
    )

    _number_unique = models.Constraint(
        "UNIQUE(number)",
        "El número de pedimento ya existe.",
    )

    @api.depends("number", "customs_id", "date")
    def _compute_name(self):
        for rec in self:
            parts = []

            if rec.number:
                parts.append(rec.number)

            if rec.customs_id:
                customs_name = rec.customs_id.city or rec.customs_id.name
                parts.append(customs_name)

            if rec.date:
                parts.append(rec.date.strftime("%d-%b-%Y").lower())

            rec.name = " - ".join(parts)

    @api.constrains("number")
    def _check_pedimento_number_format(self):
        pattern = r"^\d{2}\s\d{2}\s\d{4}\s\d{7}$"

        for rec in self:
            if rec.number and not re.match(pattern, rec.number):
                raise ValidationError(
                    self.env._(
                        "¡Error! El formato del número de pedimento es incorrecto. "
                        "El formato debe ser:15 48 3009 0001234."
                    )
                )
