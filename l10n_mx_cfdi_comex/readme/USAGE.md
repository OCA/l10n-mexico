## Import pedimentos

Assign a pedimento to a landed cost before validation to copy it to the
related lots. When invoicing products received with pedimentos, import details
are appended to invoice lines and pedimento numbers are sent in the CFDI
concepts (independent of CCE export).

## Export — Comercio Exterior 2.0

1. Set the product **Tariff Code** (fracción arancelaria).
2. Ensure issuer and customer partners have street, ZIP, country, and state
   (SAT domicilio fields).
3. On the invoice **Other Info** tab, set **Incoterm** (standard Odoo field).
4. On the **COMEX / CCE** tab, enable **Comercio Exterior (CCE)** and fill:
   - Clave de pedimento (default ``A1``)
   - Tipo cambio USD (MXN per 1 USD)
   - Optional certificado de origen / observaciones / destinatario
5. On invoice lines (optional columns), set **Valor dólares** and customs
   quantity / unit / unit value as needed.
6. Generate the CFDI as usual. The builder sets ``Exportacion=02`` and attaches
   the CCE complement.
