from odoo import fields, models


class Partner(models.Model):
    _inherit = "res.partner"

    # Add a new field to the res.partner model, called tax_regime with SAT tax regime
    # source https://www.cfdi.org.mx/catalogos-de-cfdi/regimen-fiscal/
    tax_regime = fields.Many2one(
        "l10n_mx_catalogs.c_regimen_fiscal", string="Fiscal Regime"
    )

    cfdi_use_id = fields.Many2one("l10n_mx_catalogs.c_uso_cfdi", string="CFDI Usage")
    payment_method_id = fields.Many2one(
        "l10n_mx_catalogs.c_metodo_pago", string="Payment Method"
    )
    payment_form_id = fields.Many2one(
        "l10n_mx_catalogs.c_forma_pago", string="Payment Form"
    )
