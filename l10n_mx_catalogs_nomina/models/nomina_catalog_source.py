from odoo import api, fields, models


class NominaCatalogSource(models.Model):
    """Where each payroll catalog in this module came from.

    SAT stamps every catalog with its own version, revision and publication
    date, and they move independently: two catalogs shipped in the same
    spreadsheet can be years apart. Keeping the stamp next to the data is what
    lets anyone tell, without guessing, whether the module is behind the
    published catalogs.
    """

    _name = "l10n_mx_catalogs.nomina_catalog_source"
    _description = "Procedencia de los catálogos SAT de nómina"
    _rec_name = "display_name"
    _order = "catalog"

    catalog = fields.Char(
        string="Catálogo",
        required=True,
        help="Nombre del catálogo tal como lo publica el SAT, p. ej. c_TipoPercepcion.",
    )
    model = fields.Char(string="Modelo", required=True)
    version = fields.Char(string="Versión")
    revision = fields.Char(string="Revisión")
    publication_date = fields.Date(string="Fecha de publicación")

    display_name = fields.Char(
        string="Nombre completo",
        compute="_compute_display_name",
        store=True,
    )

    _catalog_uniq = models.Constraint(
        "unique (catalog)",
        "Solo puede existir una procedencia por catálogo.",
    )

    @api.depends("catalog", "version", "revision")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "{} v{} rev {}".format(
                rec.catalog or "", rec.version or "", rec.revision or ""
            )
