from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_mx_cfdi_dangerous_material = fields.Selection(
        [("no", "No"), ("yes", "Sí"), ("optional", "Opcional")],
        string="Material peligroso CFDI",
        default="no",
        required=True,
        help="Valor de la columna 'Material peligroso' de la clave BienesTransp "
        "en el catálogo SAT c_ClaveProdServCP:\n"
        "- No ('0'): se envía MaterialPeligroso='No' sin clave ni embalaje.\n"
        "- Sí ('1'): se envía MaterialPeligroso='Sí' con la clave, el embalaje "
        "y su descripción.\n"
        "- Opcional ('0,1'): si se captura la clave se envía como 'Sí' con la "
        "clave, el embalaje y su descripción; si no, se envía 'No'.",
    )
    # The 'cfid' typo in these field names is kept for stability.
    l10n_mx_cfid_dangerous_material_code = fields.Char(
        string="Código de Material Peligroso"
    )
    l10n_mx_cfid_dangerous_material_packaging = fields.Char(
        string="Código de Embalaje Material Peligroso"
    )
    l10n_mx_cfid_dangerous_material_packaging_descripcion = fields.Char(
        string="Descripción de Embalaje Material Peligroso"
    )

    def _l10n_mx_cfdi_is_dangerous_material(self):
        """Whether the good is reported as MaterialPeligroso="Sí"."""
        self.ensure_one()
        return self.l10n_mx_cfdi_dangerous_material == "yes" or (
            self.l10n_mx_cfdi_dangerous_material == "optional"
            and bool(self.l10n_mx_cfid_dangerous_material_code)
        )
