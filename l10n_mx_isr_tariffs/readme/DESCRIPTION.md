The withholding tariffs of article 96 LISR, the UMA and the employment
subsidy, as dated data plus the arithmetic that applies them.

## ⚠️ Read this before installing

**This module is an arithmetic evaluator of the withholding tariffs published
in Annex 8 of the RMF. It is not a payroll system and it does not compute
Mexican payroll.** In particular it does **not**:

- determine the taxable base -- the exempt income of article 93 LISR (year-end
  bonus, vacation premium, profit sharing, welfare benefits, each with its own
  cap measured in UMA) has to be separated out before anything here is called;
- perform the **monthly adjustment** of tax and subsidy that the law requires
  when salaries are paid for periods shorter than a month. Evaluated period by
  period in isolation, a worker whose income varies will receive subsidy that
  was not due, and the tax authority collects that back from the employer with
  surcharges;
- apply the fractioned calculation of article 174 RISR to extraordinary
  payments such as the year-end bonus or profit sharing. Running them through
  the ordinary tariff over-withholds;
- perform the annual settlement of article 97 LISR;
- handle a worker with more than one employer, who must elect which one applies
  the subsidy.

Using it directly in production to stamp payroll receipts, without an
integrated payroll system around it, will produce wrong withholdings.

What it does do, it does against the published source and refuses to guess.

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
- The arithmetic: given a taxable amount, a periodicity and a date, the tax
  caused, the subsidy, how much of it could be applied, and what is withheld.
  The subsidy is a credit against the tax and nothing else -- what exceeds it is
  neither paid to the worker nor carried to a later month.
- Read-only views, so the table that was applied on a given date can be checked
  against the DOF without opening the database.

## What it deliberately does not do

It does not derive a tariff for a periodicity the tax authority did not
publish. The published 7, 10 and 15 day tables are *not* the daily one
multiplied by the number of days: the rounding is done at each level and the
limits drift by up to 0.14, which is enough to move a payment into a different
bracket. Asking for a periodicity with no published tariff raises an error.

It also stays out of payroll. Article 96 governs payments assimilated to
salaries too, and the arithmetic is the same there, so it lives on its own and
depends only on `base`.

## Known scope note

The UMA is published by the statistics institute, not by the tax authority, and
it is used well beyond income tax -- social security contributions, housing
credits, fines and administrative thresholds all measure themselves in it. It
lives here because this is what needed it first; a more natural home would be a
general catalog module, and moving it later would be a sound refactor.
