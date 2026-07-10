# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class L10nMxFinancialReport(models.AbstractModel):
    _name = "l10n_mx.financial.report"
    _description = "Mexico Financial Report Engine"

    BALANCE_SHEET_ACCOUNT_TYPES = {
        "asset_receivable",
        "asset_cash",
        "asset_current",
        "asset_non_current",
        "asset_prepayments",
        "asset_fixed",
        "liability_payable",
        "liability_credit_card",
        "liability_current",
        "liability_non_current",
        "equity",
        "equity_unaffected",
    }
    PROFIT_LOSS_ACCOUNT_TYPES = {
        "income",
        "income_other",
        "expense",
        "expense_depreciation",
        "expense_direct_cost",
    }
    AGED_RECEIVABLE_ACCOUNT_TYPES = {"asset_receivable"}
    AGED_PAYABLE_ACCOUNT_TYPES = {"liability_payable"}
    AGING_BUCKETS = (30, 60, 90)

    def _get_move_line_domain(self, company, date_from, date_to):
        return [
            ("company_id", "=", company.id),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("parent_state", "=", "posted"),
            ("display_type", "not in", ("line_section", "line_note")),
        ]

    def _aggregate_account_lines(self, domain, account_types=None):
        grouped = {}
        move_lines = self.env["account.move.line"].search(domain)
        for line in move_lines:
            account = line.account_id
            if account_types and account.account_type not in account_types:
                continue
            key = account.id
            if key not in grouped:
                grouped[key] = {
                    "account_code": account.code,
                    "account_name": account.display_name,
                    "account_type": account.account_type,
                    "debit": 0.0,
                    "credit": 0.0,
                    "balance": 0.0,
                }
            grouped[key]["debit"] += line.debit
            grouped[key]["credit"] += line.credit
            grouped[key]["balance"] += line.balance
        return sorted(grouped.values(), key=lambda line: line["account_code"] or "")

    def get_trial_balance(self, company, date_from, date_to):
        domain = self._get_move_line_domain(company, date_from, date_to)
        return self._aggregate_account_lines(domain)

    def get_balance_sheet(self, company, date_from, date_to):
        domain = self._get_move_line_domain(company, date_from, date_to)
        return self._aggregate_account_lines(
            domain, account_types=self.BALANCE_SHEET_ACCOUNT_TYPES
        )

    def get_profit_and_loss(self, company, date_from, date_to):
        domain = self._get_move_line_domain(company, date_from, date_to)
        return self._aggregate_account_lines(
            domain, account_types=self.PROFIT_LOSS_ACCOUNT_TYPES
        )

    def _get_aging_bucket(self, reference_date, due_date):
        reference_date = fields.Date.to_date(reference_date)
        due_date = fields.Date.to_date(due_date) if due_date else None
        if not due_date or due_date >= reference_date:
            return "current"
        days = (reference_date - due_date).days
        for bucket in self.AGING_BUCKETS:
            if days <= bucket:
                return f"{bucket}"
        return "older"

    def _get_aged_partner_lines(self, company, date_to, account_types):
        date_to = fields.Date.to_date(date_to)
        domain = [
            ("company_id", "=", company.id),
            ("parent_state", "=", "posted"),
            ("date", "<=", date_to),
            ("display_type", "not in", ("line_section", "line_note")),
            ("account_id.account_type", "in", list(account_types)),
            ("partner_id", "!=", False),
        ]
        grouped = {}
        for line in self.env["account.move.line"].search(domain):
            partner = line.partner_id
            bucket = self._get_aging_bucket(date_to, line.date_maturity or line.date)
            key = (partner.id, bucket)
            if key not in grouped:
                grouped[key] = {
                    "partner_name": partner.display_name,
                    "partner_vat": partner.vat or "",
                    "bucket": bucket,
                    "amount": 0.0,
                }
            grouped[key]["amount"] += line.amount_residual
        return sorted(
            grouped.values(),
            key=lambda line: (line["partner_name"], line["bucket"]),
        )

    def get_aged_receivable(self, company, date_to):
        return self._get_aged_partner_lines(
            company, date_to, self.AGED_RECEIVABLE_ACCOUNT_TYPES
        )

    def get_aged_payable(self, company, date_to):
        return self._get_aged_partner_lines(
            company, date_to, self.AGED_PAYABLE_ACCOUNT_TYPES
        )

    def get_diot_lines(self, company, date_from, date_to):
        domain = self._get_move_line_domain(company, date_from, date_to) + [
            ("partner_id", "!=", False),
            ("tax_line_id", "!=", False),
            ("move_id.move_type", "in", ("in_invoice", "in_refund")),
        ]
        grouped = {}
        for line in self.env["account.move.line"].search(domain):
            partner = line.partner_id
            key = partner.id
            if key not in grouped:
                grouped[key] = {
                    "partner_name": partner.display_name,
                    "partner_vat": partner.vat or "",
                    "tax_amount": 0.0,
                    "base_amount": 0.0,
                }
            grouped[key]["tax_amount"] += abs(line.balance)
        tax_base_lines = self.env["account.move.line"].search(
            domain + [("tax_line_id", "=", False), ("tax_ids", "!=", False)]
        )
        for line in tax_base_lines:
            partner = line.partner_id
            key = partner.id
            if key not in grouped:
                grouped[key] = {
                    "partner_name": partner.display_name,
                    "partner_vat": partner.vat or "",
                    "tax_amount": 0.0,
                    "base_amount": 0.0,
                }
            grouped[key]["base_amount"] += abs(line.balance)
        return sorted(grouped.values(), key=lambda line: line["partner_name"])

    def render_diot_txt(self, lines):
        rows = []
        for line in lines:
            vat = (line.get("partner_vat") or "").replace(" ", "")
            base_amount = int(round(line.get("base_amount", 0.0)))
            tax_amount = int(round(line.get("tax_amount", 0.0)))
            rows.append(f"{vat}|{base_amount}|{tax_amount}")
        return "\n".join(rows)

    def get_report_title(self, report_type):
        selection = (
            self.env["l10n_mx.financial.report.wizard"]._fields["report_type"].selection
        )
        return dict(selection).get(report_type, report_type)

    def get_report_lines(self, report_type, company, date_from, date_to):
        report_methods = {
            "balance_sheet": self.get_balance_sheet,
            "profit_loss": self.get_profit_and_loss,
            "trial_balance": self.get_trial_balance,
            "aged_receivable": lambda company, date_from, date_to: (
                self.get_aged_receivable(company, date_to)
            ),
            "aged_payable": lambda company, date_from, date_to: (
                self.get_aged_payable(company, date_to)
            ),
            "diot": self.get_diot_lines,
        }
        method = report_methods.get(report_type)
        if not method:
            return []
        return method(company, date_from, date_to)
