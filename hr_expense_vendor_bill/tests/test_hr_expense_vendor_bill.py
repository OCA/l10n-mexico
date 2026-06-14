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

    def test_create_supplier_invoices_without_vendor(self):
        sheet = self.create_expense_report(
            {
                "payment_mode": "own_account",
                "expense_line_ids": [
                    Command.create(
                        {
                            "employee_id": self.expense_employee.id,
                            "product_id": self.product_c.id,
                            "total_amount_currency": 100.0,
                            "payment_mode": "own_account",
                            "date": self.frozen_today,
                            "company_id": self.company.id,
                            "currency_id": self.company_data["currency"].id,
                        }
                    )
                ],
            }
        )
        invoices = sheet._create_supplier_invoices()
        self.assertFalse(invoices)

    def test_action_sheet_move_post_without_moves_raises(self):
        sheet = self._create_own_account_sheet()
        with self.assertRaises(UserError):
            sheet.action_sheet_move_post()

    def test_action_sheet_move_post(self):
        sheet = self._create_own_account_sheet()
        sheet.action_submit_sheet()
        sheet.action_approve_expense_sheets()
        sheet.action_sheet_move_post()
        self.assertEqual(sheet.state, "done")
        posted_moves = sheet.account_move_ids.filtered(
            lambda move: move.state == "posted"
        )
        self.assertTrue(posted_moves)

    def test_action_reset_expense_sheets_clears_moves(self):
        sheet = self._create_own_account_sheet()
        sheet.action_submit_sheet()
        sheet.action_approve_expense_sheets()
        sheet.action_sheet_move_post()
        sheet.action_reset_expense_sheets()
        self.assertFalse(sheet.account_move_ids)
        self.assertFalse(sheet.accounting_date)

    def test_action_open_account_moves(self):
        sheet = self._create_own_account_sheet()
        invoice = sheet._create_supplier_invoices()
        action = sheet.action_open_account_moves()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "account.move")
        self.assertEqual(action["res_id"], invoice.id)
        self.assertEqual(action["view_mode"], "form")

    def test_action_open_account_moves_multiple(self):
        sheet = self._create_own_account_sheet()
        sheet._create_supplier_invoices()
        sheet._create_employee_reimbursement_invoice()
        action = sheet.action_open_account_moves()
        self.assertEqual(len(sheet.account_move_ids), 2)
        self.assertNotIn("res_id", action)

    def test_res_config_settings_reimbursement_accounts(self):
        settings = self.env["res.config.settings"].create(
            {
                "company_id": self.company.id,
                "hr_expense_reimbursement_debit_account_id": self.company_data[
                    "default_account_expense"
                ].id,
                "hr_expense_reimbursement_credit_account_id": self.company_data[
                    "default_account_payable"
                ].id,
            }
        )
        settings.execute()
        self.assertEqual(
            self.company.hr_expense_reimbursement_debit_account_id,
            self.company_data["default_account_expense"],
        )
        self.assertEqual(
            self.company.hr_expense_reimbursement_credit_account_id,
            self.company_data["default_account_payable"],
        )

    def test_approve_company_account_does_not_create_vendor_invoices(self):
        sheet = self.create_expense_report()
        sheet.action_submit_sheet()
        sheet.action_approve_expense_sheets()
        self.assertFalse(
            sheet.account_move_ids.filtered(lambda move: move.expense_sheet_id)
        )

    def test_action_sheet_move_post_company_account(self):
        sheet = self.create_expense_report()
        sheet.action_submit_sheet()
        sheet.action_approve_expense_sheets()
        sheet.action_sheet_move_post()
        self.assertTrue(sheet.account_move_ids)

    def test_action_reset_company_account_sheet(self):
        sheet = self.create_expense_report()
        sheet.action_submit_sheet()
        sheet.action_approve_expense_sheets()
        sheet.action_sheet_move_post()
        sheet.action_reset_expense_sheets()
        self.assertFalse(sheet.accounting_date)

    def test_create_employee_reimbursement_without_work_contact(self):
        employee = self.env["hr.employee"].create({"name": "No Contact Employee"})
        sheet = self.create_expense_report(
            {
                "employee_id": employee.id,
                "payment_mode": "own_account",
                "expense_line_ids": [
                    Command.create(
                        {
                            "employee_id": employee.id,
                            "product_id": self.product_c.id,
                            "total_amount_currency": 100.0,
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
        with self.assertRaises(UserError):
            sheet._create_employee_reimbursement_invoice()

    def test_reconcile_without_credit_account_raises(self):
        self.company.write({"hr_expense_reimbursement_credit_account_id": False})
        sheet = self._create_own_account_sheet()
        with self.assertRaises(UserError):
            sheet._reconcile_account_lines()

    def test_create_supplier_invoices_multiple_vendors(self):
        vendor2 = self.env["res.partner"].create({"name": "Vendor 2"})
        sheet = self.create_expense_report(
            {
                "payment_mode": "own_account",
                "expense_line_ids": [
                    Command.create(
                        {
                            "employee_id": self.expense_employee.id,
                            "product_id": self.product_c.id,
                            "total_amount_currency": 100.0,
                            "vendor_id": self.vendor.id,
                            "payment_mode": "own_account",
                            "date": self.frozen_today,
                            "company_id": self.company.id,
                            "currency_id": self.company_data["currency"].id,
                        }
                    ),
                    Command.create(
                        {
                            "employee_id": self.expense_employee.id,
                            "product_id": self.product_c.id,
                            "total_amount_currency": 50.0,
                            "vendor_id": vendor2.id,
                            "payment_mode": "own_account",
                            "date": self.frozen_today,
                            "company_id": self.company.id,
                            "currency_id": self.company_data["currency"].id,
                        }
                    ),
                ],
            }
        )
        invoices = sheet._create_supplier_invoices()
        self.assertEqual(len(invoices), 2)
        self.assertEqual(set(invoices.mapped("partner_id")), {self.vendor, vendor2})

    def test_create_employee_reimbursement_skips_zero_amount(self):
        sheet = self.create_expense_report(
            {
                "payment_mode": "own_account",
                "expense_line_ids": [
                    Command.create(
                        {
                            "employee_id": self.expense_employee.id,
                            "product_id": self.product_c.id,
                            "total_amount_currency": 0.0,
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
        invoices = sheet._create_employee_reimbursement_invoice()
        self.assertFalse(invoices)

    def test_payment_state_keeps_super_for_standard_moves(self):
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Test line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                        }
                    )
                ],
            }
        )
        move._compute_payment_state()
        self.assertNotEqual(move.payment_state, "not_paid")
