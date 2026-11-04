This module links the CFDIs downloaded from the SAT by `l10n_mx_sat` with
purchase orders.

A new **Bill from SAT** button on confirmed purchase orders opens a wizard
listing the received CFDIs of the vendor that are not yet linked to a vendor
bill. The selected CFDI is attached to the bill created from the purchase
order, so the standard XML import of the accounting app can process it, and
the SAT document keeps a reference to the bill so it cannot be used twice.

The module also provides the abstract model
`l10n_mx_sat.document.selector.mixin` so other modules can offer the same
CFDI selection on their own records.
