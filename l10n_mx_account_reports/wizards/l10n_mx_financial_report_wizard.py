# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64

from odoo import api, fields, models
from odoo.exceptions import UserError


class L10nMxFinancialReportWizard(models.TransientModel):
    _name = "l10n_mx.financial.report.wizard"
    _description = "Mexico Financial Report Wizard"

    report_type = fields.Selection(
        selection=[
            ("balance_sheet", "Balance Sheet"),
            ("profit_loss", "Profit and Loss"),
            ("trial_balance", "Trial Balance"),
            ("aged_receivable", "Aged Accounts Receivable"),
            ("aged_payable", "Aged Accounts Payable"),
            ("diot", "DIOT"),
        ],
        required=True,
    )
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for wizard in self:
            if (
                wizard.date_from
                and wizard.date_to
                and wizard.date_from > wizard.date_to
            ):
                raise UserError(
                    self.env._("The start date must be before the end date.")
                )

    def _get_report_engine(self):
        return self.env["l10n_mx.financial.report"]

    def _get_report_lines(self):
        self.ensure_one()
        return self._get_report_engine().get_report_lines(
            self.report_type,
            self.company_id,
            self.date_from,
            self.date_to,
        )

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "l10n_mx_account_reports.action_report_l10n_mx_financial"
        ).report_action(self)

    def action_export_diot_txt(self):
        self.ensure_one()
        if self.report_type != "diot":
            raise UserError(
                self.env._("The DIOT export is only available for the DIOT report.")
            )
        engine = self._get_report_engine()
        content = engine.render_diot_txt(self._get_report_lines())
        attachment = self.env["ir.attachment"].create(
            {
                "name": "diot.txt",
                "type": "binary",
                "datas": base64.b64encode(content.encode()),
                "mimetype": "text/plain",
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        defaults.setdefault("date_from", today.replace(day=1))
        defaults.setdefault("date_to", today)
        return defaults

    @api.model
    def action_open_wizard(self, report_type):
        wizard = self.create({"report_type": report_type})
        return {
            "type": "ir.actions.act_window",
            "name": self._get_report_engine().get_report_title(report_type),
            "res_model": self._name,
            "view_mode": "form",
            "target": "new",
            "res_id": wizard.id,
        }
