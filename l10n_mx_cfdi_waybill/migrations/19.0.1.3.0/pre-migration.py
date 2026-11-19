from odoo.tools import sql


def migrate(cr, version):
    """Map the former boolean indicator to the new three-state selection.

    Runs before the ORM loads the models, while the old column still exists.
    """
    if not sql.column_exists(
        cr, "product_template", "l10n_mx_cfdi_dangerous_material_indicator"
    ):
        return
    if not sql.column_exists(cr, "product_template", "l10n_mx_cfdi_dangerous_material"):
        sql.create_column(
            cr, "product_template", "l10n_mx_cfdi_dangerous_material", "varchar"
        )
    cr.execute(
        """
        UPDATE product_template
           SET l10n_mx_cfdi_dangerous_material =
               CASE WHEN l10n_mx_cfdi_dangerous_material_indicator
                    THEN 'yes' ELSE 'no' END
        """
    )
