Otros modulos pueden usar los metodos de `res.company` para interactuar con el SAT:

- `company.l10n_mx_sat_get_client()` -> retorna instancia de `SatClient`
- `company.l10n_mx_sat_get_token()` -> autentica y retorna token SAT
- `company.l10n_mx_sat_get_credentials()` -> retorna tupla (cer_der, key_der, password)

Para cambiar la implementacion del cliente SAT (por ejemplo, usar otra libreria),
sobreescribir `l10n_mx_sat_get_client()` en un modulo que herede `res.company`.
