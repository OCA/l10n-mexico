This module provides the data from the Mexican tax authority (SAT).

## Features

- Necessary fields for electronic invoicing
- Necessary fields for electronic payroll
- Official data from Servicio de Administración Tributaria (SAT

## Updates

To update the catalogs, you need to:

* Go to [this page of the SAT website](http://omawww.sat.gob.mx/tramitesyservicios/Paginas/anexo_20.htm)
* Download the XLS file for "Catálogos CFDI Versión 4.0 (xls)"
* Run the [script](https://github.com/OCA/l10n-mexico/blob/17.0/l10n_mx_catalogs/import_catalogs_xls.py)

```shell
pip install xlrd
./import_catalogs_xls.py catCFDI_V_4_YYYYMMDD.xls
```
