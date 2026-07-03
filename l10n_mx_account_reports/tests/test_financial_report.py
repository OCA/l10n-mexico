# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import L10nMxReportsTestCase


@tagged("post_install", "-at_install")
class TestL10nMxFinancialReport(L10nMxReportsTestCase):
    def test_trial_balance_contains_posted_lines(self):
        lines = self.report_engine.get_trial_balance(
            self.company_data["company"],
            "2026-06-01",
            "2026-06-30",
        )
        self.assertTrue(lines)
        self.assertTrue(any(line["debit"] or line["credit"] for line in lines))

    def test_balance_sheet_filters_account_types(self):
        lines = self.report_engine.get_balance_sheet(
            self.company_data["company"],
            "2026-06-01",
            "2026-06-30",
        )
        for line in lines:
            self.assertIn(
                line["account_type"],
                self.report_engine.BALANCE_SHEET_ACCOUNT_TYPES,
            )

    def test_profit_and_loss_filters_account_types(self):
        lines = self.report_engine.get_profit_and_loss(
            self.company_data["company"],
            "2026-06-01",
            "2026-06-30",
        )
        for line in lines:
            self.assertIn(
                line["account_type"],
                self.report_engine.PROFIT_LOSS_ACCOUNT_TYPES,
            )

    def test_aged_receivable_and_payable(self):
        receivable_lines = self.report_engine.get_aged_receivable(
            self.company_data["company"],
            "2026-06-30",
        )
        payable_lines = self.report_engine.get_aged_payable(
            self.company_data["company"],
            "2026-06-30",
        )
        self.assertIsInstance(receivable_lines, list)
        self.assertIsInstance(payable_lines, list)

    def test_aging_bucket(self):
        reference_date = date(2026, 6, 30)
        self.assertEqual(
            self.report_engine._get_aging_bucket(reference_date, reference_date),
            "current",
        )
        self.assertEqual(
            self.report_engine._get_aging_bucket(reference_date, date(2026, 5, 1)),
            "60",
        )

    def test_diot_lines_and_txt(self):
        lines = self.report_engine.get_diot_lines(
            self.company_data["company"],
            "2026-06-01",
            "2026-06-30",
        )
        self.assertTrue(lines)
        content = self.report_engine.render_diot_txt(lines)
        self.assertIn("XAXX010101000", content)

    def test_get_report_lines_unknown_type(self):
        lines = self.report_engine.get_report_lines(
            "unknown",
            self.company_data["company"],
            "2026-06-01",
            "2026-06-30",
        )
        self.assertEqual(lines, [])

    def test_get_report_title(self):
        title = self.report_engine.get_report_title("trial_balance")
        self.assertEqual(title, "Trial Balance")


@tagged("post_install", "-at_install")
class TestL10nMxFinancialReportWizard(L10nMxReportsTestCase):
    def test_default_get(self):
        defaults = self.env["l10n_mx.financial.report.wizard"].default_get(
            ["date_from", "date_to"]
        )
        self.assertIn("date_from", defaults)
        self.assertIn("date_to", defaults)

    def test_action_open_wizard(self):
        action = self.env["l10n_mx.financial.report.wizard"].action_open_wizard(
            "balance_sheet"
        )
        self.assertEqual(action["res_model"], "l10n_mx.financial.report.wizard")
        wizard = self.env["l10n_mx.financial.report.wizard"].browse(action["res_id"])
        self.assertEqual(wizard.report_type, "balance_sheet")

    def test_action_print_pdf(self):
        wizard = self._wizard("trial_balance")
        report = self.env.ref("l10n_mx_account_reports.action_report_l10n_mx_financial")
        action = wizard.action_print_pdf()
        self.assertEqual(action["type"], "ir.actions.report")
        self.assertEqual(action["report_name"], report.report_name)
        self.assertEqual(action["report_type"], report.report_type)

    def test_action_export_diot_txt(self):
        wizard = self._wizard("diot")
        action = wizard.action_export_diot_txt()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertIn("/web/content/", action["url"])

    def test_action_export_diot_txt_wrong_report(self):
        wizard = self._wizard("trial_balance")
        with self.assertRaises(UserError):
            wizard.action_export_diot_txt()

    def test_invalid_dates(self):
        with self.assertRaises(UserError):
            self.env["l10n_mx.financial.report.wizard"].create(
                {
                    "report_type": "trial_balance",
                    "date_from": "2026-06-30",
                    "date_to": "2026-06-01",
                    "company_id": self.company_data["company"].id,
                }
            )

    def test_report_values(self):
        wizard = self._wizard("profit_loss")
        values = self.env[
            "report.l10n_mx_account_reports.report_financial"
        ]._get_report_values(wizard.ids)
        self.assertEqual(values["report_title"], "Profit and Loss")
        self.assertTrue(values["report_lines"])
