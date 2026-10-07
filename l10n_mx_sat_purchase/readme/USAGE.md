## Whole CFDI

1. Open a confirmed purchase order and click **Bill from SAT**.
2. Pick the CFDI in the **SAT CFDI** field: it searches the received CFDIs
   of the vendor in the currency of the order that are not cancelled nor
   linked to another bill, by folio, issuer, total or UUID. When exactly one
   CFDI has the total of the orders, or is within the total tolerance, it
   comes pre-selected.
3. Click **Create Bill**. The vendor bill is created from the purchase order
   lines with the XML attached. A warning is shown when the CFDI total does
   not match the orders total.

## By lines

1. Open the wizard from a purchase order, or from the CFDI with **Match with
   Purchase Orders** in **SAT > Documents**, which takes every purchase order
   of the vendor that is pending to bill. Purchase orders can be added or
   removed in the wizard: the mapping already done is kept.
2. Set **Match** to *By lines*. The **Concepts** tab lists the concepts of
   the CFDI (vendor code, description, quantity, SAT unit, unit price,
   amount and taxes) with the purchase order line proposed for each one:
   - by `NoIdentificacion`, equal to the **Internal Reference** of the
     product or to its **Vendor Product Code** for the vendor;
   - else by description, ignoring case and accents, equal to the
     description of the purchase order line, the name of the product or its
     **Vendor Product Name**;
   - else the only line with the same unit price.

   Among several candidates, the ones with the same unit price go first,
   then from the oldest order to the newest. A concept that does not fit in
   the pending quantity of a line is split to take the next ones.
3. Review the proposal: change the purchase order line or the quantity to
   bill of each concept, and use **Split** to bill the rest of a concept in
   another purchase order line. Concepts whose price differs from the
   purchase order beyond the tolerance are highlighted. A concept without
   purchase order line is billed as a line without purchase order, with the
   product optionally set in the **Product** column.
4. Click **Create Bill**. No purchase order line can exceed its quantity
   pending to bill. The bill is created in draft with one line per concept:
   product, taxes and analytic distribution of the purchase order line,
   quantity of the CFDI and, depending on the configuration, unit price and
   discount of the CFDI. The purchase orders are its origin, the series and
   folio of the CFDI its reference and the date of the CFDI its bill date.
   The XML is attached; a warning tells when the amount to bill differs from
   the CFDI subtotal and a note in the chatter when the bill total differs
   from the CFDI total.

When `product_unspsc` is installed, the quantity and the unit price of a
concept are converted from its SAT unit (`ClaveUnidad`) to the unit of the
purchase order line.

The **Not billed** filter of **SAT > Documents** lists the received CFDIs that
still have no vendor bill.
