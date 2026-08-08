Income tax withholding on salaries for the Mexican localization: the tariffs of
article 96 LISR and the employment subsidy, as dated data plus the calculation.

## Features

- The tariffs published in Annex 8 of the RMF -- daily, 7, 10 and 15 days,
  monthly and yearly -- with the date they came into force and the date they
  were published in the DOF.
- The UMA, with its own validity. It changes on **1 February**, not on
  1 January, which is what makes January's subsidy different from the rest of
  the year's.
- The employment subsidy stored as **a percentage of the monthly UMA**, with
  the income limit and the proration divisor, so the amount always follows the
  published UMA instead of a figure copied at some point in time.
- The calculation: given a taxable amount, a periodicity and a date, the tax
  caused, the subsidy, how much of it could be applied, and what is withheld.
  The subsidy is a credit against the tax and nothing else -- what exceeds it is
  neither paid to the worker nor carried to a later month.

## What it deliberately does not do

It does not derive a tariff for a periodicity the tax authority did not
publish. The published 7, 10 and 15 day tables are *not* the daily one
multiplied by the number of days: the rounding is done at each level and the
limits drift by up to 0.14, which is enough to move a payment into a different
bracket. Asking for a periodicity with no published tariff raises an error.

It also stays out of payroll. Article 96 governs payments assimilated to
salaries too, and the calculation is the same there, so it lives on its own and
depends only on `base`.
