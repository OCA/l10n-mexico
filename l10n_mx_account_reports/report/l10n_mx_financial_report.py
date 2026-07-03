# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class ReportL10nMxFinancial(models.AbstractModel):
    _name = "report.l10n_mx_account_reports.report_financial"
    _description = "Mexico Financial Report"

    def _get_report_values(self, docids, data=None):
        wizard = self.env["l10n_mx.financial.report.wizard"].browse(docids)
        wizard.ensure_one()
        engine = self.env["l10n_mx.financial.report"]
        return {
            "doc_ids": docids,
            "doc_model": wizard._name,
            "docs": wizard,
            "company": wizard.company_id,
            "date_from": wizard.date_from,
            "date_to": wizard.date_to,
            "report_title": engine.get_report_title(wizard.report_type),
            "report_lines": wizard._get_report_lines(),
        }
