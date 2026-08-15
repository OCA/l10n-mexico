This module adds the KNRECEPCION addenda for Kuehne+Nagel and allows you to
generate electronic invoices (CFDI 4.0) with the required reception block.

The addenda is inserted under `cfdi:Addenda` with this structure:

- `kn:KNRECEPCION`
  - `kn:Tipo`
    - `kn:FacturasKN`
      - `kn:Purchase_Order`
      - `kn:FileNumber_GL`
      - `kn:Branch_Centre`
      - `kn:TransportRef`
