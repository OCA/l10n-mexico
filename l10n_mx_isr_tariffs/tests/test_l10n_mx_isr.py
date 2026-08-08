"""Every expected number here was worked out by hand from the DOF documents.

They are not recordings of what the code returned. The point of a tax module is
that it agrees with the published tariff, so the fixtures are the arithmetic of
article 96 LISR applied to the bracket that Annex 8 prints, written out in the
docstring of each test. If a refactor changes a result, one of the two is wrong
and the comment says which.
"""

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestIsr(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tariff = cls.env["l10n_mx.isr.tariff"]
        cls.Uma = cls.env["l10n_mx.uma"]
        cls.Subsidy = cls.env["l10n_mx.employment.subsidy"]
        cls.Isr = cls.env["l10n_mx.isr"]
        cls.january = "2026-01-15"
        cls.june = "2026-06-15"

    # ------------------------------------------------------------------
    # The data
    # ------------------------------------------------------------------

    def test_six_tariffs_with_eleven_brackets_each(self):
        tariffs = self.Tariff.search([("date_start", "=", "2026-01-01")])
        self.assertEqual(
            set(tariffs.mapped("periodicity")),
            {"daily", "weekly", "ten_day", "fortnight", "monthly", "annual"},
        )
        for tariff in tariffs:
            with self.subTest(periodicity=tariff.periodicity):
                self.assertEqual(len(tariff.line_ids), 11)
                self.assertEqual(str(tariff.dof_publication), "2025-12-28")

    def test_monthly_tariff_matches_the_dof_at_both_ends(self):
        tariff = self.Tariff.get_for_date("monthly", self.june)
        lines = tariff.line_ids.sorted("lower_limit")
        first, last = lines[0], lines[-1]
        self.assertEqual((first.lower_limit, first.upper_limit), (0.01, 844.59))
        self.assertEqual((first.fixed_fee, first.rate), (0.0, 1.92))
        self.assertEqual(last.lower_limit, 425642.00)
        self.assertFalse(last.upper_limit)
        self.assertEqual((last.fixed_fee, last.rate), (133488.54, 35.00))

    def test_brackets_chain_without_gaps(self):
        for tariff in self.Tariff.search([]):
            lines = tariff.line_ids.sorted("lower_limit")
            with self.subTest(tariff=tariff.periodicity):
                for previous, current in zip(lines, lines[1:], strict=False):
                    self.assertAlmostEqual(
                        current.lower_limit - previous.upper_limit, 0.01, places=2
                    )

    # ------------------------------------------------------------------
    # Article 96: fixed fee + excess x rate
    # ------------------------------------------------------------------

    def test_monthly_tax(self):
        """20,000.00 falls in 17,533.65-35,362.83: 1,856.84 + 2,466.35 x 21.36%."""
        tariff = self.Tariff.get_for_date("monthly", self.june)
        self.assertEqual(tariff.compute_tax(20000.00), 2383.65)

    def test_fortnight_tax(self):
        """8,000.00 falls in 7,225.96-8,651.40: 660.75 + 774.04 x 17.92%."""
        tariff = self.Tariff.get_for_date("fortnight", self.june)
        self.assertEqual(tariff.compute_tax(8000.00), 799.46)

    def test_daily_tax(self):
        """500.00 falls in 481.74-576.76: 44.05 + 18.26 x 17.92%."""
        tariff = self.Tariff.get_for_date("daily", self.june)
        self.assertEqual(tariff.compute_tax(500.00), 47.32)

    def test_weekly_tax(self):
        """3,000.00 falls in 2,900.88-3,372.11: 232.96 + 99.12 x 16.00%."""
        tariff = self.Tariff.get_for_date("weekly", self.june)
        self.assertEqual(tariff.compute_tax(3000.00), 248.82)

    def test_ten_day_tax(self):
        """5,000.00 falls in 4,817.31-5,767.60: 440.50 + 182.69 x 17.92%."""
        tariff = self.Tariff.get_for_date("ten_day", self.june)
        self.assertEqual(tariff.compute_tax(5000.00), 473.24)

    def test_annual_tax(self):
        """300,000.00 falls in 210,403.70-424,353.97: 22,282.14 + 89,596.30 x 21.36%."""
        tariff = self.Tariff.get_for_date("annual", self.june)
        self.assertEqual(tariff.compute_tax(300000.00), 41419.91)

    def test_first_bracket_and_open_bracket(self):
        tariff = self.Tariff.get_for_date("monthly", self.june)
        # 500.00 is in the first bracket: 0.00 + 500.00 x 1.92%.
        self.assertEqual(tariff.compute_tax(500.00), 9.60)
        # 500,000.00 is past the last limit: 133,488.54 + 74,358.00 x 35.00%.
        self.assertEqual(tariff.compute_tax(500000.00), 159513.84)

    def test_no_taxable_base_no_tax(self):
        tariff = self.Tariff.get_for_date("monthly", self.june)
        self.assertEqual(tariff.compute_tax(0.0), 0.0)

    def test_negative_base_is_rejected_by_the_tariff_too(self):
        """Same answer from either entry point, so nothing slips through."""
        tariff = self.Tariff.get_for_date("monthly", self.june)
        with self.assertRaises(UserError):
            tariff.compute_tax(-100.0)

    # ------------------------------------------------------------------
    # A tariff SAT did not publish is an error, not a guess
    # ------------------------------------------------------------------

    def test_unpublished_periodicity_raises(self):
        with self.assertRaises(UserError) as caught:
            self.Tariff.get_for_date("biweekly_14", self.june)
        self.assertIn("Anexo 8", str(caught.exception))

    def test_date_before_any_tariff_raises(self):
        with self.assertRaises(UserError):
            self.Tariff.get_for_date("monthly", "2020-06-15")

    # ------------------------------------------------------------------
    # The UMA changes on 1 February, not on 1 January
    # ------------------------------------------------------------------

    def test_uma_in_january_is_still_the_previous_years(self):
        self.assertEqual(self.Uma.get_for_date("2026-01-15").amount_monthly, 3439.46)
        self.assertEqual(self.Uma.get_for_date("2026-01-31").amount_monthly, 3439.46)

    def test_uma_changes_on_the_first_of_february(self):
        self.assertEqual(self.Uma.get_for_date("2026-02-01").amount_monthly, 3566.22)
        self.assertEqual(self.Uma.get_for_date("2026-06-15").amount_daily, 117.31)

    # ------------------------------------------------------------------
    # The subsidy comes out of the formula, not out of the recitals
    # ------------------------------------------------------------------

    def test_monthly_subsidy_january(self):
        """Transitory rule: 15.59% of the UMA in force, which in January is 2025's.

        3,439.46 x 15.59% = 536.21.
        """
        subsidy = self.Subsidy.get_for_date(self.january)
        self.assertEqual(subsidy.uma_percent, 15.59)
        self.assertEqual(subsidy.monthly_amount(self.january), 536.21)

    def test_monthly_subsidy_rest_of_the_year(self):
        """15.02% of the 2026 UMA: 3,566.22 x 15.02% = 535.65.

        Not 536.22. That figure appears in the decree's recitals, written before
        INEGI published the 2026 UMA; the operative article says to apply the
        percentage to the monthly UMA, and this is what that yields.
        """
        subsidy = self.Subsidy.get_for_date(self.june)
        self.assertEqual(subsidy.uma_percent, 15.02)
        self.assertEqual(subsidy.monthly_amount(self.june), 535.65)

    def test_prorated_for_a_period_shorter_than_a_month(self):
        """535.65 / 30.4 x 15 = 264.30."""
        subsidy = self.Subsidy.get_for_date(self.june)
        self.assertEqual(subsidy.compute(8000.0, self.june, days=15), 264.30)

    def test_proration_never_exceeds_a_full_month(self):
        subsidy = self.Subsidy.get_for_date(self.june)
        self.assertEqual(subsidy.compute(8000.0, self.june, days=31), 535.65)

    def test_single_payment_covering_several_months(self):
        subsidy = self.Subsidy.get_for_date(self.june)
        self.assertEqual(subsidy.compute(8000.0, self.june, months=3), 1606.95)

    def test_income_limit_is_inclusive(self):
        subsidy = self.Subsidy.get_for_date(self.june)
        self.assertEqual(subsidy.compute(11492.66, self.june), 535.65)
        self.assertEqual(subsidy.compute(11492.67, self.june), 0.0)

    def test_days_and_months_together_are_rejected(self):
        subsidy = self.Subsidy.get_for_date(self.june)
        with self.assertRaises(UserError):
            subsidy.compute(8000.0, self.june, days=15, months=2)

    def test_the_recital_amount_is_nowhere_in_the_data(self):
        """536.22 must not have been hardcoded anywhere."""
        for subsidy in self.Subsidy.search([]):
            self.assertNotEqual(subsidy.monthly_amount(subsidy.date_start), 536.22)

    # ------------------------------------------------------------------
    # The two pieces composed
    # ------------------------------------------------------------------

    def test_withholding_above_the_subsidy_limit(self):
        """20,000.00 a month: tax 2,383.65, no subsidy, so that is withheld."""
        result = self.Isr.compute_withholding(20000.00, "monthly", self.june)
        self.assertEqual(result["tax"], 2383.65)
        self.assertEqual(result["subsidy"], 0.0)
        self.assertEqual(result["withheld"], 2383.65)
        self.assertEqual(result["subsidy_forgone"], 0.0)

    def test_subsidy_above_the_tax_is_lost_not_paid(self):
        """8,000.00 a month: tax 420.95 + 831.48 x 10.88% = 511.42, subsidy 535.65.

        Only 511.42 of the subsidy can be applied and nothing is withheld. The
        remaining 24.23 is **not** handed to the worker: the decree says that
        when the tax is smaller than the subsidy the difference "no podrá
        aplicarse contra el impuesto que resulte a su cargo posteriormente, ni
        se entregará cantidad alguna".
        """
        result = self.Isr.compute_withholding(8000.00, "monthly", self.june)
        self.assertEqual(result["tax"], 511.42)
        self.assertEqual(result["subsidy"], 535.65)
        self.assertEqual(result["subsidy_applied"], 511.42)
        self.assertEqual(result["withheld"], 0.0)
        self.assertEqual(result["subsidy_forgone"], 24.23)

    def test_a_shorter_period_needs_the_monthly_income_spelled_out(self):
        """The subsidy limit is monthly; a fortnight's base is not that figure."""
        with self.assertRaises(UserError) as caught:
            self.Isr.compute_withholding(8000.00, "fortnight", self.june)
        self.assertIn("ingreso mensual", str(caught.exception))

    def test_a_shorter_period_needs_its_days_spelled_out(self):
        """A fortnight is 15 or 16 days depending on the half of the month."""
        with self.assertRaises(UserError) as caught:
            self.Isr.compute_withholding(
                3000.00, "fortnight", self.june, monthly_income=6000.00
            )
        self.assertIn("días del periodo", str(caught.exception))

    def test_fortnightly_withholding_with_the_monthly_income_given(self):
        """Base 8,000.00 a fortnight: tax 799.46; monthly income 16,000.00 is over
        the limit, so there is no subsidy."""
        result = self.Isr.compute_withholding(
            8000.00, "fortnight", self.june, monthly_income=16000.00, days=15
        )
        self.assertEqual(result["tax"], 799.46)
        self.assertEqual(result["subsidy"], 0.0)
        self.assertEqual(result["withheld"], 799.46)

    def test_fortnightly_withholding_with_subsidy(self):
        """Base 3,000.00 a fortnight falls in 416.71-3,537.15: 7.95 + 2,583.29 x 6.40%.

        That is 173.28. Monthly income 6,000.00 is under the limit, so the
        subsidy is the fortnightly share, 264.30, and 91.02 is paid to the
        worker.
        """
        result = self.Isr.compute_withholding(
            3000.00, "fortnight", self.june, monthly_income=6000.00, days=15
        )
        self.assertEqual(result["tax"], 173.28)
        self.assertEqual(result["subsidy"], 264.30)
        self.assertEqual(result["subsidy_applied"], 173.28)
        self.assertEqual(result["withheld"], 0.0)
        self.assertEqual(result["subsidy_forgone"], 91.02)

    def test_subsidy_can_be_switched_off(self):
        """Severance and other payments the decree excludes take no subsidy."""
        result = self.Isr.compute_withholding(
            8000.00, "monthly", self.june, with_subsidy=False
        )
        self.assertEqual(result["subsidy"], 0.0)
        self.assertEqual(result["withheld"], 511.42)

    def test_january_and_june_do_not_withhold_the_same(self):
        """The subsidy percentage changes between them, so neither does the result."""
        january = self.Isr.compute_withholding(8000.00, "monthly", self.january)
        june = self.Isr.compute_withholding(8000.00, "monthly", self.june)
        self.assertEqual(january["subsidy"], 536.21)
        self.assertEqual(june["subsidy"], 535.65)
        self.assertNotEqual(january["subsidy_forgone"], june["subsidy_forgone"])

    # ------------------------------------------------------------------
    # Caller mistakes surface instead of turning into plausible numbers
    # ------------------------------------------------------------------

    def test_zero_days_is_not_a_full_month(self):
        """`if days:` would swallow a zero and pay the whole month."""
        subsidy = self.Subsidy.get_for_date(self.june)
        with self.assertRaises(UserError):
            subsidy.compute(8000.0, self.june, days=0)

    def test_negative_period_is_rejected(self):
        subsidy = self.Subsidy.get_for_date(self.june)
        with self.assertRaises(UserError):
            subsidy.compute(8000.0, self.june, months=-1)

    def test_fractional_period_is_rejected(self):
        subsidy = self.Subsidy.get_for_date(self.june)
        with self.assertRaises(UserError):
            subsidy.compute(8000.0, self.june, months=1.5)

    def test_a_missing_date_is_rejected(self):
        """Falling back to today would tax a payslip with the wrong year."""
        with self.assertRaises(UserError):
            self.Tariff.get_for_date("monthly", False)
        with self.assertRaises(UserError):
            self.Uma.get_for_date(None)

    def test_overlapping_validity_windows_are_refused(self):
        with self.assertRaises(ValidationError):
            self.Uma.create(
                {
                    "date_start": "2026-06-01",
                    "amount_daily": 1.0,
                    "amount_monthly": 30.4,
                    "amount_annual": 364.8,
                }
            )

    def test_a_year_with_no_published_tariff_fails_loudly(self):
        """The annex is published per year; 2027 must not reuse 2026 in silence."""
        with self.assertRaises(UserError):
            self.Tariff.get_for_date("monthly", "2027-03-15")

    def test_negative_base_is_rejected(self):
        with self.assertRaises(UserError):
            self.Isr.compute_withholding(-100.0, "monthly", self.june)

    def test_annual_tariff_does_not_take_the_monthly_subsidy(self):
        """The yearly tariff is the annual settlement; the subsidy was already
        given month by month and is not subtracted a second time."""
        with self.assertRaises(UserError) as caught:
            self.Isr.compute_withholding(
                300000.00, "annual", self.june, monthly_income=25000.00
            )
        self.assertIn("with_subsidy=False", str(caught.exception))
        result = self.Isr.compute_withholding(
            300000.00, "annual", self.june, with_subsidy=False
        )
        self.assertEqual(result["withheld"], 41419.91)

    def test_validity_window_must_be_ordered(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.Uma.create(
                {
                    "date_start": "2030-02-01",
                    "date_end": "2029-02-01",
                    "amount_daily": 1.0,
                    "amount_monthly": 30.4,
                    "amount_annual": 364.8,
                }
            )
            self.Uma.flush_model()

    def test_divisor_cannot_be_zero(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.Subsidy.create(
                {
                    "date_start": "2030-01-01",
                    "uma_percent": 15.0,
                    "income_limit": 1000.0,
                    "monthly_divisor": 0.0,
                }
            )
            self.Subsidy.flush_model()
