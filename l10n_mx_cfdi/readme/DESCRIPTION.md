This module provides the configuration used by electronic invoicing for Mexico:

- Multi-PAC integration via satcfdi (Finkok, Diverza, Prodigia, Comercio Digital,
  SW Sapien, MYSuite, Facturama).
- Local CSD management for CFDI sealing when the PAC uses ``stamp()``.
- Facturama Multiemisor CSD upload on issuer registration (required before
  ``issue()``).
- Management of different series and CFDI issuers for the same company.

**CFDI × PAC capability matrix**

| Flow | Finkok | Diverza | Prodigia | Com. Digital | SW Sapien | MYSuite | Facturama |
|------|:------:|:-------:|:--------:|:------------:|:---------:|:-------:|:---------:|
| Path | issue() | issue() | stamp() | stamp() | issue() | stamp() | issue() Multiemisor / Web |
| Ingreso (I) | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Egreso (E) | Conditional | Conditional | Conditional | Conditional | Conditional | Conditional | Conditional |
| Pago (P) | Conditional | Conditional | Conditional | Conditional | Conditional | Conditional | Conditional |
| Traslado / Carta Porte | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Pedimentos on concepts | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Full CCE complement | Conditional | Conditional | Conditional | Conditional | Conditional | Conditional | Conditional |
| Cancel (API) | Conditional | Yes | No | No | Yes | No | Yes |
| Cancel with acuse | Conditional | Unknown | No | No | Unknown | No | Conditional |

**Legend**

- **Yes**: supported end-to-end via this module + satcfdi for that PAC.
- **Conditional**:
  - Egreso: requires a fully reconciled refund (``amount_residual == 0``).
  - Pago: auto-stamp only for reconciled inbound payments on **PPD** invoices;
    manual stamping needs valid payment CFDI data.
  - Finkok cancel: requires company FIEL via ``l10n_mx_sat`` (signer).
  - Facturama cancel acuse: may be empty; the module shows status/message when
    the PAC omits the acuse.
  - Full CCE: built by ``l10n_mx_cfdi_comex`` (``Exportacion=02`` +
    ``cce20.ComercioExterior``). Stamp PACs (Prodigia, Comercio Digital,
    MYSuite) and XML-issue PACs (Finkok, Diverza, SW) can stamp sealed XML with
    CCE (live PAC acceptance not exhaustively retested here). Facturama
    Multiemisor does **not** support CCE; when CCE is present the module
    switches to FacturamaWeb (same user/password; account-profile CSD).
- **No**:
  - Cancel API is not exposed in satcfdi for Prodigia, Comercio Digital, and
    MYSuite (``supports_cancel=False``).
- **Unknown**: acuse availability depends on the PAC response (Diverza /
  SW Sapien).
- **Path**: Finkok, Diverza, SW Sapien, and Facturama use ``issue()``; Prodigia,
  Comercio Digital, and MYSuite use local CSD seal + ``stamp()``. Facturama is
  Multiemisor by default (**Registrar** uploads the CSD); FacturamaWeb is used
  automatically for Comercio Exterior.
- Pedimentos on concepts are not the full CCE complement; the Facturama adapter
  maps ``NumerosPedimento``.
