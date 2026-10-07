Configure the FIEL credentials and the download of received CFDIs in
`l10n_mx_sat` (**Settings > Companies > SAT** tab).

The vendor must have the RFC of the CFDI issuer in its **Tax ID** field, and
the company RFC must match the receiver of the CFDI.

In **Purchase > Configuration > Settings > Invoicing > Bills from SAT
CFDIs** set, for each company:

- **Match**: how CFDIs are matched with purchase orders by default, *Whole
  CFDI* or *By lines*. A vendor can have its own value in the **Sales &
  Purchase** tab of its form (**Match SAT CFDIs**), and the user can change
  it on each bill.
- **Price by lines**: whether the bill lines matched by lines take the unit
  price of the CFDI (default) or the one of the purchase order.
- **Total tolerance**: a CFDI is proposed for the purchase orders when its
  total differs from theirs by this amount at most.
- **Price tolerance (%)**: a concept of a CFDI is highlighted when its unit
  price differs from the one of the purchase order line by more than this
  percentage.
- **Learn vendor codes**: when a concept of a CFDI is mapped by hand to a
  purchase order line, its `NoIdentificacion` is kept as the **Vendor
  Product Code** of the vendor pricelist of the product, so the next CFDI
  with that code is matched alone.

To match by lines without reviewing each concept, set the code the vendor
uses in its CFDIs (`NoIdentificacion`) as the **Vendor Product Code** of the
vendor pricelist of the product, or keep **Learn vendor codes** enabled.
