Once configured, the module will automatically download vendor bills from
SAT and create them as draft entries in the Vendor Bills section.

Each imported bill includes:

- Partner resolved by RFC (auto-created if not found)
- Tax matching (IVA, ISR, IEPS) using pre-configured Mexican taxes
- The original CFDI XML attached to the bill
- A chatter message with the UUID reference

Review the draft bills and validate them as needed. The CFDI UUID is
stored for deduplication — the same invoice will never be imported twice.

You can check the status of download requests in
Accounting > Configuration > SAT Downloads.
