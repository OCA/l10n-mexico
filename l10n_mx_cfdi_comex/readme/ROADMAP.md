- Import full SAT catalogs for `c_INCOTERM`, `c_ClavePedimento`,
  `c_UnidadAduana`, and `c_MotivoTraslado` into `l10n_mx_catalogs_comex`
  (Many2one selectors instead of Char codes).
- Auto-default TipoCambioUSD from Banxico / `currency_rate_update_banxico`
  when available.
- Richer Destinatario / Propietario flows and DescripcionesEspecificas on
  mercancías.
- Live PAC certification matrix for CCE on each provider.
