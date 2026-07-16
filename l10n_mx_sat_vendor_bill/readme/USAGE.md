When ``l10n_mx_sat`` downloads received CFDI XML files, this module
creates matching draft vendor bills automatically.

Each imported bill includes:

- Partner resolved by RFC (auto-created if not found)
- Tax matching (IVA, ISR, IEPS) using pre-configured Mexican taxes
- The original CFDI XML attached to the bill
- A chatter message with the UUID reference

Review the draft bills and validate them as needed. The CFDI UUID is
stored for deduplication — the same invoice will never be imported twice.

Monitor SAT downloads under Accounting > Configuration > SAT Downloads.
