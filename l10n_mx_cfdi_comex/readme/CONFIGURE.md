Install `l10n_mx_catalogs_comex` and `l10n_mx_cfdi_account` before this module.

Configure tariff codes on product templates and create pedimentos from
**Inventory > Operations > Pedimentos**.

For CCE exports, keep partner addresses complete and use the standard invoice
**Incoterm** field. Prefer Banxico USD rates for **Tipo cambio USD**.

SAT catalog imports for `c_INCOTERM`, `c_ClavePedimento`, and `c_UnidadAduana`
are not shipped as full data tables yet; codes are entered as Char fields
(Incoterm reuses `account.incoterms.code`). See ROADMAP.
