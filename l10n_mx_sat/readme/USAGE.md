Other modules can use the methods on `res.company` to interact with
the SAT:

- `company.l10n_mx_sat_get_client()` -> returns a `SatClient` instance
- `company.l10n_mx_sat_get_token()` -> authenticates and returns the
  SAT token
- `company.l10n_mx_sat_get_credentials()` -> returns a tuple
  `(cer_der, key_der, password)`

To swap the SAT client implementation (for example, to use a different
library), override `l10n_mx_sat_get_client()` in a module that
inherits `res.company`.
