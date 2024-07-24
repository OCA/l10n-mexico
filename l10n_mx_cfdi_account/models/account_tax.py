from odoo import models


class AccountTax(models.Model):
    _inherit = "account.tax"

    def extract_l10n_mx_tax_code(self):
        self.ensure_one()
        if "ISR" in self.name:
            return "ISR"
        elif "IEPS" in self.name:
            return "IEPS"
        else:
            return "IVA"

    def extract_is_retention(self):
        self.ensure_one()
        return "RET" in self.name
