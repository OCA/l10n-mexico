# Copyright 2026 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.hr_expense.tests.common import TestExpenseCommon


@tagged("post_install", "-at_install")
class TestHrExpenseVendorBill(TestExpenseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env["res.partner"].create({"name": "Test Vendor"})
        cls.company = cls.company_data["company"]
        cls.company.write(
            {
                "hr_expense_reimbursement_debit_account_id": cls.company_data[
                    "default_account_expense"
                ].id,
                "hr_expense_reimbursement_credit_account_id": cls.company_data[
                    "default_account_payable"
                ].id,
            }
        )

    def _create_own_account_sheet(self, total_amount=100.0):
        return self.create_expense_report(
            {
                "payment_mode": "own_account",
                "expense_line_ids": [
                    Command.create(
                        {
                            "employee_id": self.expense_employee.id,
                            "product_id": self.product_c.id,
                            "total_amount_currency": total_amount,
                            "vendor_id": self.vendor.id,
                            "payment_mode": "own_account",
                            "date": self.frozen_today,
                            "company_id": self.company.id,
                            "currency_id": self.company_data["currency"].id,
                        }
                    )
                ],
            }
        )

    def test_vendor_id_on_expense(self):
        expense = self.create_expense({"vendor_id": self.vendor.id})
        self.assertEqual(expense.vendor_id, self.vendor)

    def test_create_supplier_invoices(self):
        sheet = self._create_own_account_sheet()
        invoices = sheet._create_supplier_invoices()
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices.partner_id, self.vendor)
        self.assertEqual(invoices.expense_sheet_id, sheet)
        self.assertEqual(invoices.move_type, "in_invoice")

    def test_create_employee_reimbursement_invoice(self):
        sheet = self._create_own_account_sheet(total_amount=250.0)
        invoices = sheet._create_employee_reimbursement_invoice()
        employee_partner = sheet.employee_id.sudo().work_contact_id
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices.partner_id, employee_partner)
        self.assertEqual(invoices.move_type, "in_invoice")
        self.assertIn(sheet, invoices.expense_sheet_id)

    def test_reimbursement_payment_state(self):
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.expense_employee.work_contact_id.id,
                "is_employee_reimbursement": True,
            }
        )
        move._compute_payment_state()
        self.assertEqual(move.payment_state, "not_paid")

    def test_missing_reimbursement_accounts_raises(self):
        self.company.write(
            {
                "hr_expense_reimbursement_debit_account_id": False,
                "hr_expense_reimbursement_credit_account_id": False,
            }
        )
        sheet = self._create_own_account_sheet()
        with self.assertRaises(UserError):
            sheet._create_employee_reimbursement_invoice()

    def test_approve_own_account_creates_invoices(self):
        sheet = self._create_own_account_sheet()
        sheet.action_submit_sheet()
        sheet.action_approve_expense_sheets()
        employee_partner = sheet.employee_id.sudo().work_contact_id
        supplier_invoices = sheet.account_move_ids.filtered(
            lambda move: move.partner_id == self.vendor
        )
        employee_invoices = sheet.account_move_ids.filtered(
            lambda move: move.partner_id == employee_partner
        )
        self.assertEqual(len(supplier_invoices), 1)
        self.assertEqual(len(employee_invoices), 1)
        self.assertEqual(supplier_invoices.expense_sheet_id, sheet)
