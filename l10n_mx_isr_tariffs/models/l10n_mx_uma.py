from odoo import api, fields, models
from odoo.exceptions import UserError

from .utils import check_no_overlap, required_date


class Uma(models.Model):
    """Unidad de Medida y Actualización, as published by INEGI.

    Its value changes once a year but **not on 1 January**: article 5 of the law
    that governs it puts the new value in force on 1 February. That one month of
    overlap is not a detail — the employment subsidy of January is computed with
    the previous year's UMA, so a model that keyed the UMA by year alone would
    be wrong for a twelfth of every year.
    """

    _name = "l10n_mx.uma"
    _description = "Unidad de Medida y Actualización"
    _rec_name = "display_name"
    _order = "date_start desc"

    date_start = fields.Date(string="Inicio de vigencia", required=True, index=True)
    date_end = fields.Date(
        string="Fin de vigencia",
        help="La UMA deja de aplicarse a partir de esta fecha.",
    )
    amount_daily = fields.Float(string="Valor diario", digits=(16, 2), required=True)
    amount_monthly = fields.Float(string="Valor mensual", digits=(16, 2), required=True)
    amount_annual = fields.Float(string="Valor anual", digits=(16, 2), required=True)
    dof_publication = fields.Date(string="Publicación en el DOF")

    display_name = fields.Char(
        string="Nombre completo", compute="_compute_display_name", store=True
    )

    _date_start_uniq = models.Constraint(
        "unique (date_start)",
        "Solo puede haber un valor de la UMA por fecha de inicio de vigencia.",
    )
    _dates_ordered = models.Constraint(
        "check (date_end is null or date_end > date_start)",
        "El fin de vigencia de la UMA debe ser posterior a su inicio.",
    )

    @api.constrains("date_start", "date_end")
    def _check_no_overlap(self):
        check_no_overlap(self, key_fields=())

    @api.depends("date_start", "amount_daily")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "UMA {} — {}".format(
                rec.date_start or "", rec.amount_daily or 0.0
            )

    @api.model
    def get_for_date(self, date):
        """The UMA in force on ``date``. Raises when none is loaded."""
        date = required_date(self, date)
        uma = self.search(
            [
                ("date_start", "<=", date),
                "|",
                ("date_end", "=", False),
                ("date_end", ">", date),
            ],
            order="date_start desc",
            limit=1,
        )
        if not uma:
            raise UserError(
                self.env._(
                    "No hay un valor de la UMA cargado para la fecha %(date)s.",
                    date=date,
                )
            )
        return uma
