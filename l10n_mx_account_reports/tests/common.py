# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class L10nMxReportsTestCase(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.report_engine = cls.env["l10n_mx.financial.report"]
        cls.company_data["company"].external_report_layout_id = cls.env.ref(
            "web.external_layout_standard"
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Vendor MX",
                "vat": "XAXX010101000",
            }
        )
        cls._create_vendor_bill()

    @classmethod
    def _create_vendor_bill(cls):
        invoice = cls.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": cls.partner.id,
                "invoice_date": "2026-06-15",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Service",
                            "quantity": 1.0,
                            "price_unit": 1000.0,
                            "account_id": cls.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [
                                (6, 0, cls.company_data["default_tax_purchase"].ids)
                            ],
                        },
                    )
                ],
            }
        )
        invoice.action_post()

    def _wizard(self, report_type):
        return self.env["l10n_mx.financial.report.wizard"].create(
            {
                "report_type": report_type,
                "date_from": "2026-06-01",
                "date_to": "2026-06-30",
                "company_id": self.company_data["company"].id,
            }
        )
