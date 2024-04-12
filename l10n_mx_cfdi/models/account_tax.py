from odoo import models
from odoo.exceptions import UserError


class AccountTax(models.Model):
    _inherit = "account.tax"

    def extract_l10n_mx_tax_code(self):
        self.ensure_one()
        if "ISR" in self.name:
            return "ISR"
        elif "IVA" in self.name:
            return "IVA"
        elif "IEPS" in self.name:
            return "IEPS"

        raise UserError("No se pudo extraer el código de impuesto de %s" % self.name)

    def extract_is_retention(self):
        self.ensure_one()
        return "RET" in self.name
