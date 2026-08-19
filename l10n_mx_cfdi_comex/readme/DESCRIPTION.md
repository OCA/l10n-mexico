This module adds Mexican foreign trade (COMEX) compliance on top of CFDI invoicing.

**Features**

- Pedimento management linked to inventory lots (import path)
- Tariff code (fracción arancelaria) on products
- Import details on invoice lines for Mexican companies
- Pedimento numbers in CFDI concept ``InformacionAduanera`` / ``NumerosPedimento``
- Pedimento propagation from landed costs to lots
- **Complemento Comercio Exterior 2.0** on customer invoices:
  ``Exportacion=02`` plus satcfdi ``cce20.ComercioExterior`` (Emisor/Receptor/
  Destinatario domicilios, mercancías, TipoCambioUSD, TotalUSD)
- Reuses the standard invoice **Incoterm** field (``invoice_incoterm_id`` /
  ``account.incoterms``) for SAT ``c_INCOTERM``; no duplicate Incoterm field

**PAC notes**

- Stamp / XML-issue PACs can stamp sealed CFDIs that include CCE.
- Facturama Multiemisor cannot map CCE; ``l10n_mx_cfdi`` switches to
  FacturamaWeb when the complement is present.
