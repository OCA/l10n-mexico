# Copyright (C) 2026 Odoo Community Association (OCA).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import tagged

from . import common


@tagged("post_install", "-at_install")
class TestMisReportByPartner(common.L10nMxReportsTestCase):
    """Partner-level (detail_groupby = partner_id) MIS reports.

    These reports rely on the ``detail_groupby`` feature of ``mis_builder``
    (OCA/mis-builder#817), not yet merged upstream. When the installed
    ``mis_builder`` does not provide the ``detail_groupby`` field, module
    install fails on the CSV column, so these tests skip if the field is
    missing. Aging buckets are MIS instance periods (Today / Saldo vencido /
    0-30 / 31-60 / 61-90 / 91-120 / +120), matching the live Mexican chart
    expressions ``balp[105%]`` and ``balp[201%]``.
    """

    def setUp(self):
        super().setUp()
        if "detail_groupby" not in self.env["mis.report.kpi"]._fields:
            self.skipTest("mis_builder detail_groupby unavailable (needs fork PR #817)")

    REPORT_XMLIDS = [
        "l10n_mx_account_reports.mis_report_aged_receivable_by_move",
        "l10n_mx_account_reports.mis_report_aged_receivable_by_due",
        "l10n_mx_account_reports.mis_report_aged_payable_by_move",
        "l10n_mx_account_reports.mis_report_aged_payable_by_due",
        "l10n_mx_account_reports.mis_report_diot",
    ]
    INSTANCE_XMLIDS = [
        "l10n_mx_account_reports.mis_instance_aged_receivable_by_move",
        "l10n_mx_account_reports.mis_instance_aged_receivable_by_due",
        "l10n_mx_account_reports.mis_instance_aged_payable_by_move",
        "l10n_mx_account_reports.mis_instance_aged_payable_by_due",
        "l10n_mx_account_reports.mis_instance_diot_by_partner",
    ]

    def test_01_reports_use_partner_detail(self):
        """Templates/instances load and KPIs expand by partner."""
        for xmlid in self.REPORT_XMLIDS:
            report = self.env.ref(xmlid)
            self.assertTrue(report.kpi_ids, f"{xmlid} has no KPIs")
            for kpi in report.kpi_ids:
                self.assertEqual(
                    kpi.detail_groupby,
                    "partner_id",
                    f"{xmlid} KPI {kpi.name} is not partner-expandable",
                )
        for xmlid in self.INSTANCE_XMLIDS:
            instance = self.env.ref(xmlid)
            self.assertTrue(instance.period_ids, f"{xmlid} has no period")

    def test_02_aged_receivable_partner_rows(self):
        """The AR (by due date) report expands one detail row per partner."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": "2026-06-15",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Service",
                            "quantity": 1.0,
                            "price_unit": 1000.0,
                            "account_id": self.company_data[
                                "default_account_income"
                            ].id,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        instance = self.env.ref(
            "l10n_mx_account_reports.mis_instance_aged_receivable_by_due"
        )
        instance.company_id = self.company_data["company"]
        instance.target_move = "all"
        matrix = instance._compute_matrix()
        rows = list(matrix.iter_rows())
        detail_rows = [r for r in rows if r.detail_id is not None]
        self.assertTrue(detail_rows, "no partner detail rows produced")
        detail_by_id = {r.detail_id: r for r in detail_rows}
        self.assertIn(self.partner.id, detail_by_id)
        total = sum(
            (c.val or 0) for c in detail_by_id[self.partner.id].iter_cells() if c
        )
        self.assertAlmostEqual(total, 1000.0, places=2)
