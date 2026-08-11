This module provides the SAT catalogs of the payroll complement
(*complemento de nómina* 1.2) for the Mexican localization.

## Features

- The thirteen catalogs of the payroll complement, as data:
  `c_Banco`, `c_OrigenRecurso`, `c_PeriodicidadPago`, `c_RiesgoPuesto`,
  `c_TipoContrato`, `c_TipoDeduccion`, `c_TipoHoras`, `c_TipoIncapacidad`,
  `c_TipoJornada`, `c_TipoNomina`, `c_TipoOtroPago`, `c_TipoPercepcion`,
  `c_TipoRegimen`.
- **Validity dates per key.** SAT publishes a start and an end date for every
  key, and keys do expire. Both dates are kept, so a payroll document can be
  checked against the keys that were usable during its own period instead of
  the ones usable today.
- **Provenance.** Each catalog records the version, revision and publication
  date SAT stamped on it, so it is possible to tell at a glance whether the
  shipped data is behind the published one.
- Keys keep the exact string form of the schema (`001`, `01`, `1`, `O`), which
  is what travels in the XML.
