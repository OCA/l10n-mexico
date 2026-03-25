# Copyright 2025 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("mx", "account.tax.group")
    def _get_mx_l10n_mx_tax_account_tax_group(self):
        return self._parse_csv("mx", "account.tax.group", module="l10n_mx_tax")

    @template("mx", "account.account")
    def _get_mx_l10n_mx_tax_account_account(self):
        return self._parse_csv("mx", "account.account", module="l10n_mx_tax")

    @template("mx", "account.tax")
    def _get_mx_l10n_mx_tax_account_tax(self):
        return self._parse_csv("mx", "account.tax", module="l10n_mx_tax")
