from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round

from .utils import check_no_overlap, required_date


class EmploymentSubsidy(models.Model):
    """Subsidio para el empleo, per the decree that grants it.

    Stored as **a percentage of the monthly UMA**, never as an amount. The
    decree in force says the subsidy is "la cantidad que resulte de multiplicar
    el valor mensual de la Unidad de Medida y Actualización por 15.02%"; the
    figure quoted in its recitals was written before INEGI published that year's
    UMA and does not match what the formula yields. Storing the percentage keeps
    the module tied to the operative text instead of to an estimate.
    """

    _name = "l10n_mx.employment.subsidy"
    _description = "Subsidio para el empleo"
    _rec_name = "display_name"
    _order = "date_start desc"

    date_start = fields.Date(string="Inicio de vigencia", required=True, index=True)
    date_end = fields.Date(
        string="Fin de vigencia",
        help="El parámetro deja de aplicarse a partir de esta fecha.",
    )
    uma_percent = fields.Float(
        string="% de la UMA mensual",
        digits=(16, 4),
        required=True,
        help="Porcentaje del valor mensual de la UMA que constituye el subsidio.",
    )
    income_limit = fields.Float(
        string="Límite de ingresos mensuales",
        digits=(16, 2),
        required=True,
        help="Ingreso mensual base del ISR por encima del cual no hay subsidio.",
    )
    monthly_divisor = fields.Float(
        string="Divisor mensual",
        digits=(16, 4),
        required=True,
        default=30.4,
        help="Divisor para prorratear el subsidio en periodos menores a un mes.",
    )
    dof_publication = fields.Date(string="Publicación en el DOF")

    display_name = fields.Char(
        string="Nombre completo", compute="_compute_display_name", store=True
    )

    _date_start_uniq = models.Constraint(
        "unique (date_start)",
        "Ya existe un parámetro del subsidio con esa fecha de inicio.",
    )
    _dates_ordered = models.Constraint(
        "check (date_end is null or date_end > date_start)",
        "El fin de vigencia del subsidio debe ser posterior a su inicio.",
    )
    _divisor_positive = models.Constraint(
        "check (monthly_divisor > 0)",
        "El divisor mensual del subsidio debe ser mayor que cero.",
    )
    _percent_in_range = models.Constraint(
        "check (uma_percent >= 0 and uma_percent <= 100)",
        "El porcentaje de la UMA debe estar entre 0 y 100.",
    )

    @api.constrains("date_start", "date_end")
    def _check_no_overlap(self):
        check_no_overlap(self, key_fields=())

    @api.depends("date_start", "uma_percent")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "Subsidio {} — {}% UMA".format(
                rec.date_start or "", rec.uma_percent or 0.0
            )

    @api.model
    def get_for_date(self, date):
        """The subsidy parameters in force on ``date``."""
        date = required_date(self, date)
        subsidy = self.search(
            [
                ("date_start", "<=", date),
                "|",
                ("date_end", "=", False),
                ("date_end", ">", date),
            ],
            order="date_start desc",
            limit=1,
        )
        if not subsidy:
            raise UserError(
                self.env._(
                    "No hay parámetros del subsidio para el empleo cargados para "
                    "la fecha %(date)s.",
                    date=date,
                )
            )
        return subsidy

    def monthly_amount(self, date):
        """The full monthly subsidy on ``date``: monthly UMA x percentage."""
        self.ensure_one()
        uma = self.env["l10n_mx.uma"].get_for_date(date)
        return float_round(
            uma.amount_monthly * self.uma_percent / 100.0, precision_digits=2
        )

    def compute(self, monthly_income, date, days=None, months=None):
        """Subsidy for one payment.

        ``monthly_income`` is the income that serves as the basis for the
        monthly income tax, excluding severance-type payments, which the decree
        leaves out of the limit test; the caller is what knows which lines those
        are.

        ``days`` prorates a period shorter than a month, ``months`` scales a
        single payment covering two or more months. They are mutually exclusive;
        passing neither returns the plain monthly amount.
        """
        self.ensure_one()
        if days and months:
            raise UserError(
                self.env._(
                    "El subsidio se prorratea por días o se multiplica por meses, "
                    "no ambas cosas en el mismo pago."
                )
            )
        # Zero or negative is not "no proration": days=0 would silently fall
        # through to the full monthly amount, and months=-1 would return a
        # negative subsidy. Both are caller mistakes worth surfacing.
        for label, value in (("días", days), ("meses", months)):
            if value is None:
                continue
            if int(value) != value:
                raise UserError(
                    self.env._(
                        "El número de %(label)s del pago debe ser entero; "
                        "se recibió %(value)s.",
                        label=label,
                        value=value,
                    )
                )
            if value <= 0:
                raise UserError(
                    self.env._(
                        "El número de %(label)s del pago debe ser mayor que cero; "
                        "se recibió %(value)s.",
                        label=label,
                        value=value,
                    )
                )
        if float_compare(monthly_income, self.income_limit, precision_digits=2) > 0:
            return 0.0

        monthly = self.monthly_amount(date)
        if months:
            return float_round(monthly * months, precision_digits=2)
        if days:
            prorated = monthly / self.monthly_divisor * days
            # The decree caps the prorated amount at the full monthly figure, so
            # a 31-day period does not pay more subsidy than a month does.
            return float_round(min(prorated, monthly), precision_digits=2)
        return monthly
