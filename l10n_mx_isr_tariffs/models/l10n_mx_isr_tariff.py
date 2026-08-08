from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round

from .utils import check_no_overlap, required_date


class IsrTariff(models.Model):
    """A tariff of article 96 LISR, as published in Annex 8 of the RMF.

    One record per periodicity and per period of validity. The tariffs change
    every year the accumulated inflation triggers an update, and a payslip has
    to be taxed with the tariff that was in force on its own date, so validity
    is part of the data rather than something the caller has to remember.
    """

    _name = "l10n_mx.isr.tariff"
    _description = "Tarifa del ISR (art. 96 LISR, Anexo 8 RMF)"
    _rec_name = "display_name"
    _order = "date_start desc, periodicity"

    name = fields.Char(string="Nombre", required=True)
    periodicity = fields.Selection(
        [
            ("daily", "Diaria"),
            ("weekly", "Semanal (7 días)"),
            ("ten_day", "Decenal (10 días)"),
            ("fortnight", "Quincenal (15 días)"),
            ("monthly", "Mensual"),
            ("annual", "Anual (ejercicio)"),
        ],
        string="Periodicidad",
        required=True,
        index=True,
    )
    date_start = fields.Date(string="Inicio de vigencia", required=True, index=True)
    date_end = fields.Date(
        string="Fin de vigencia",
        help="La tarifa deja de aplicarse a partir de esta fecha.",
    )
    dof_publication = fields.Date(string="Publicación en el DOF")
    line_ids = fields.One2many("l10n_mx.isr.tariff.line", "tariff_id", string="Tramos")

    display_name = fields.Char(
        string="Nombre completo", compute="_compute_display_name", store=True
    )

    _periodicity_date_uniq = models.Constraint(
        "unique (periodicity, date_start)",
        "Ya existe una tarifa de esa periodicidad con esa fecha de inicio.",
    )
    _dates_ordered = models.Constraint(
        "check (date_end is null or date_end > date_start)",
        "El fin de vigencia de la tarifa debe ser posterior a su inicio.",
    )

    @api.constrains("date_start", "date_end", "periodicity")
    def _check_no_overlap(self):
        check_no_overlap(self, key_fields=("periodicity",))

    @api.depends("name", "periodicity", "date_start")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{} ({})".format(rec.name or "", rec.date_start or "")

    @api.model
    def get_for_date(self, periodicity, date):
        """The tariff of ``periodicity`` in force on ``date``.

        Raises rather than falling back. A tariff that SAT did not publish for a
        periodicity cannot be derived from another one: the published 7, 10 and
        15 day tables are *not* the daily table multiplied by the number of days
        -- SAT rounds at each level and the limits drift by up to 0.14, which is
        enough to move a payment across a bracket boundary.
        """
        date = required_date(self, date)
        tariff = self.search(
            [
                ("periodicity", "=", periodicity),
                ("date_start", "<=", date),
                "|",
                ("date_end", "=", False),
                ("date_end", ">", date),
            ],
            order="date_start desc",
            limit=1,
        )
        if not tariff:
            label = dict(self._fields["periodicity"].selection).get(
                periodicity, periodicity
            )
            raise UserError(
                self.env._(
                    "El SAT no publica una tarifa del ISR %(periodicity)s vigente "
                    "al %(date)s. Las tarifas publicadas en el Anexo 8 son diaria, "
                    "de 7, 10 y 15 días, mensual y anual; una periodicidad distinta "
                    "no se puede derivar de ellas sin alterar la retención.",
                    periodicity=label,
                    date=date,
                )
            )
        return tariff

    def compute_tax(self, taxable_base):
        """ISR for ``taxable_base`` under this tariff, per article 96 LISR.

        fixed fee + (excess over the lower limit x rate).
        """
        self.ensure_one()
        if taxable_base < 0:
            raise UserError(self.env._("La base gravable no puede ser negativa."))
        base = float_round(taxable_base, precision_digits=2)
        if not base:
            return 0.0
        line = self._get_bracket(base)
        excess = base - line.lower_limit
        return float_round(
            line.fixed_fee + excess * line.rate / 100.0, precision_digits=2
        )

    def _get_bracket(self, base):
        self.ensure_one()
        # Compared with float_compare: the limits land on exact cents and a
        # binary float can sit a hair below one, which at a boundary means the
        # payment is taxed under the wrong bracket.
        for line in self.line_ids.sorted("lower_limit"):
            above = float_compare(base, line.lower_limit, precision_digits=2) >= 0
            below = not line.upper_limit or (
                float_compare(base, line.upper_limit, precision_digits=2) <= 0
            )
            if above and below:
                return line
        raise UserError(
            self.env._(
                "La tarifa %(tariff)s no tiene un tramo que cubra la base "
                "%(base)s. Los tramos cargados están incompletos.",
                tariff=self.display_name,
                base=base,
            )
        )


class IsrTariffLine(models.Model):
    """One bracket of a tariff."""

    _name = "l10n_mx.isr.tariff.line"
    _description = "Tramo de la tarifa del ISR"
    _order = "tariff_id, lower_limit"

    tariff_id = fields.Many2one(
        "l10n_mx.isr.tariff",
        string="Tarifa",
        required=True,
        ondelete="cascade",
        index=True,
    )
    lower_limit = fields.Float(string="Límite inferior", digits=(16, 2), required=True)
    upper_limit = fields.Float(
        string="Límite superior",
        digits=(16, 2),
        help="Vacío en el último tramo: 'En adelante'.",
    )
    fixed_fee = fields.Float(string="Cuota fija", digits=(16, 2), required=True)
    rate = fields.Float(
        string="% sobre el excedente",
        digits=(16, 2),
        required=True,
        help="Por ciento para aplicarse sobre el excedente del límite inferior.",
    )
