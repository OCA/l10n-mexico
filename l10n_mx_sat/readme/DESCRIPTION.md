Modulo base para conectar Odoo con el portal del SAT usando credenciales FIEL.

Provee:

- Campos para almacenar certificado (.cer), llave privada (.key) y contrasena FIEL
  en la configuracion de la empresa.
- Boton para probar la conexion con el SAT.
- Adaptador (`SatClient`) que encapsula la comunicacion con el SAT via cfdiclient.
  Otros modulos pueden usar este adaptador sin depender directamente de cfdiclient.
- Factory `company.l10n_mx_sat_get_client()` para obtener una instancia del adaptador.
  Se puede sobreescribir via `_inherit` para cambiar la implementacion.

Este modulo NO realiza operaciones de negocio por si solo. Es una base para
modulos como `l10n_mx_sat_vendor_bill` que descargan facturas del SAT.
