from odoo import _, models
from odoo.exceptions import UserError


class AccountTax(models.Model):
    _inherit = "account.tax"

    def extract_l10n_mx_tax_code(self):
        self.ensure_one()
        if "ISR" in self.invoice_label:
            return "ISR"
        elif "IVA" in self.invoice_label:
            return "IVA"
        elif "IEPS" in self.invoice_label:
            return "IEPS"
        elif "VAT" in self.invoice_label:
            return "VAT"
        raise UserError(_("Cannot extract the tax code from %s") % self.invoice_label)

    def extract_is_retention(self):
        self.ensure_one()
        return "RET" in self.invoice_label
