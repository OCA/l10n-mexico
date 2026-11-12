- Matching by lines takes the taxes of the purchase order line, not the ones
  of the CFDI.
- Units of measure are only converted when `product_unspsc` is installed and
  the SAT unit of the concept has a unit of measure.
- A bill is created from a single CFDI.
