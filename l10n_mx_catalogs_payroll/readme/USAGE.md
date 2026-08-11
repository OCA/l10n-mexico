Read a catalog like any other model:

```python
percepciones = env["l10n_mx_catalogs.c_tipo_percepcion"].search([])
```

Ask for the keys usable on a given date -- the date of the document you are
building, not today:

```python
usable = env["l10n_mx_catalogs.c_tipo_deduccion"].search_in_force("2026-01-15")
```

Check a single key:

```python
key = env["l10n_mx_catalogs.c_tipo_deduccion"].search([("code", "=", "063")])
key.is_in_force("2026-04-15")  # False: it expired on 2026-03-01
```

An end date is exclusive: SAT states that an expired key cannot be used *from*
the date shown in the "fecha fin de vigencia" column onwards.

## Updating the catalogs

Download the two official files from
https://www.sat.gob.mx/portal/public/tramites/complemento-de-nomina
(tab *Información especializada*): the catalog spreadsheet and the catalog
schema. Then regenerate the data:

```shell
python3 import_catalogs_xls.py catNomina.xls catNomina.xsd
```

The importer checks the spreadsheet against the schema and refuses to write
anything if a key is present in one and missing in the other.
