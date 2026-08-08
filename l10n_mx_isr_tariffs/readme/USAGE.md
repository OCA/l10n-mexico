```python
result = env["l10n_mx.isr"].compute_withholding(
    taxable_base=8000.00,
    periodicity="monthly",
    date="2026-06-15",
)
# {'tax': 511.42, 'subsidy': 535.65, 'subsidy_applied': 511.42,
#  'withheld': 0.0, 'subsidy_forgone': 24.23}
```

`subsidy_forgone` is **not** money to hand over. The subsidy is a credit against
the tax and nothing more: when the tax is smaller, the decree says the
difference "no podrá aplicarse contra el impuesto que resulte a su cargo
posteriormente, ni se entregará cantidad alguna". It is reported so a payroll
can show it, never so it can pay it.

For a period shorter than a month, pass the monthly income and the days the
period covers. The subsidy limit is set per month, so a fortnight's taxable base
is not the figure to test it against; and the days are a property of the period,
not of its name, since a fortnightly payroll runs 15 days in the first half of
the month and 15 or 16 in the second. The module will not assume either:

```python
env["l10n_mx.isr"].compute_withholding(
    taxable_base=3000.00,
    periodicity="fortnight",
    date="2026-06-15",
    monthly_income=6000.00,
    days=15,
)
```

The pieces are usable separately:

```python
env["l10n_mx.uma"].get_for_date("2026-01-15").amount_monthly
env["l10n_mx.isr.tariff"].get_for_date("monthly", "2026-06-15").compute_tax(20000.0)
env["l10n_mx.employment.subsidy"].get_for_date("2026-06-15").monthly_amount("2026-06-15")
```

## Updating for a new year

The tariffs arrive every year in Annex 8 of the RMF, published in the DOF:

```shell
pdftotext -layout Anexo-8-RMF-YYYY.pdf anexo8.txt
python3 import_anexo8_pdf.py anexo8.txt --year YYYY \
    --dof-publication YYYY-12-28 --date-start YYYY-01-01
```

The importer checks that every tariff has its full set of brackets, that they
chain without gaps, and that no two tariffs came out identical, which is what
happens when a heading is matched in the table of contents instead of the body.

The UMA and the subsidy parameters are two short CSVs under `data/`; add a row
with the new value and its start date, and close the previous one.
