This module links the CFDIs downloaded from the SAT by `l10n_mx_sat` with
purchase orders.

A new **Bill from SAT** button on confirmed purchase orders opens a wizard
to pick one of the received CFDIs of the vendor that are not yet linked to a
vendor bill. The bill can be created in two ways:

- **Whole CFDI**: the bill takes everything pending to bill in the purchase
  orders and the XML is attached to it, so the standard XML import of the
  accounting app can process it.
- **By lines**: each concept of the CFDI is mapped to the purchase order
  line it bills, with its quantity, unit price and discount. This covers a
  CFDI that bills part of several purchase orders.

A CFDI of type E (credit note) creates a vendor credit note by lines that
lowers the billed quantities of the purchase order lines. The type of the
CFDI decides: a CFDI of type I never creates a credit note, nor a CFDI of
type E a bill. The CFDI can instead be linked to an existing bill (or
credit note) of the orders without CFDI; the one matching it by reference
or by total is proposed.

The SAT document keeps a reference to the bill so it cannot be used twice.

The module also provides the abstract model
`l10n_mx_sat.document.selector.mixin` so other modules can offer the same
CFDI selection on their own records.
