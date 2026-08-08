from odoo import api, fields, models


class SatNominaCatalog(models.AbstractModel):
    """Shared behaviour of the SAT payroll catalogs.

    Every key published by SAT carries the dates it may be used between, and
    keys do expire. A payslip has to be validated against the keys that were in
    force during *its* period, not the ones in force today, so the dates are
    part of the data instead of being dropped on import.
    """

    _name = "l10n_mx_catalogs.sat_nomina_catalog"
    _description = "Catálogo SAT del complemento de nómina"
    _rec_name = "display_name"
    _rec_names_search = ["code", "name"]
    _order = "code"

    code = fields.Char(string="Código", required=True, index=True)
    name = fields.Char(string="Descripción", required=True)
    date_start = fields.Date(string="Inicio de vigencia")
    date_end = fields.Date(
        string="Fin de vigencia",
        help="La clave no puede utilizarse a partir de esta fecha.",
    )

    display_name = fields.Char(
        string="Nombre completo",
        compute="_compute_display_name",
        store=True,
    )

    _code_uniq = models.Constraint(
        "unique (code)",
        "El código del catálogo SAT debe ser único.",
    )

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.code or ''} - {rec.name or ''}"

    @api.model
    def _in_force_domain(self, date=None):
        """Domain matching the keys usable on ``date`` (today by default).

        SAT states it plainly: a key whose validity expired "no se podrá
        utilizar a partir de la fecha indicada en la columna fecha fin de
        vigencia". The end date is therefore exclusive.
        """
        date = fields.Date.to_date(date) or fields.Date.context_today(self)
        return [
            "|",
            ("date_start", "=", False),
            ("date_start", "<=", date),
            "|",
            ("date_end", "=", False),
            ("date_end", ">", date),
        ]

    @api.model
    def search_in_force(self, date=None, domain=None):
        """Return the catalog keys usable on ``date``."""
        return self.search(self._in_force_domain(date) + (domain or []))

    def is_in_force(self, date=None):
        """Whether every key in ``self`` is usable on ``date``."""
        date = fields.Date.to_date(date) or fields.Date.context_today(self)
        return all(
            (not rec.date_start or rec.date_start <= date)
            and (not rec.date_end or rec.date_end > date)
            for rec in self
        )
