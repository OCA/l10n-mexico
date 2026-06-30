After configuration, currency rates are updated like any other OCA provider:

- On the provider form, use *Update Rates* to fetch rates for a date range.
- When automatic updates are enabled, the scheduled job refreshes rates according
  to the provider interval.

If your company currency is not MXN, Banxico rates are still fetched in MXN and
recalculated for your base currency. A warning is shown on the provider form in
that case.
