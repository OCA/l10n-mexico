#!/usr/bin/env python3
"""Regenerate the payroll catalog CSVs from the official SAT files.

Two official sources are needed, and they check each other:

* ``catNomina.xls`` -- descriptions and validity dates per key.
* ``catNomina.xsd`` -- the authoritative *string* form of every key
  (``001``, ``01``, ``1``, ``O``...). The spreadsheet stores keys as numbers,
  so ``001`` reads back as ``1.0``; the schema is what says how wide the code
  really is, and that is what travels in the XML.

Both files are published by SAT at
https://www.sat.gob.mx/portal/public/tramites/complemento-de-nomina
(tab "Informacion especializada").

The importer fails loudly when the two sources disagree: a key present in one
and missing in the other means the downloaded pair is inconsistent and must not
be turned into module data.

Usage::

    python3 import_catalogs_xls.py catNomina.xls catNomina.xsd
"""

import argparse
import csv
import logging
import os
import re
import unicodedata

import xlrd

_logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Sheet name -> (odoo model, extra columns taken from the spreadsheet).
# The spreadsheet column titles are matched loosely (accents and case are
# ignored), because SAT is not consistent about them between sheets.
CATALOGS = {
    "c_Banco": ("l10n_mx_catalogs.c_banco", {"legal_name": "nombre o razon social"}),
    "c_OrigenRecurso": ("l10n_mx_catalogs.c_origen_recurso", {}),
    "c_PeriodicidadPago": ("l10n_mx_catalogs.c_periodicidad_pago", {}),
    "c_TipoContrato": ("l10n_mx_catalogs.c_tipo_contrato", {}),
    "c_TipoDeduccion": ("l10n_mx_catalogs.c_tipo_deduccion", {}),
    "c_TipoHoras": ("l10n_mx_catalogs.c_tipo_horas", {}),
    "c_TipoIncapacidad": ("l10n_mx_catalogs.c_tipo_incapacidad", {}),
    "c_TipoJornada": ("l10n_mx_catalogs.c_tipo_jornada", {}),
    "c_TipoNomina": ("l10n_mx_catalogs.c_tipo_nomina", {}),
    "c_TipoOtroPago": ("l10n_mx_catalogs.c_tipo_otro_pago", {}),
    "c_TipoPercepcion": ("l10n_mx_catalogs.c_tipo_percepcion", {}),
    "c_TipoRegimen": ("l10n_mx_catalogs.c_tipo_regimen", {}),
    "c_RiesgoPuesto": ("l10n_mx_catalogs.c_riesgo_puesto", {}),
}

SOURCE_MODEL = "l10n_mx_catalogs.nomina_catalog_source"


def _strip_accents(value):
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _norm_header(value):
    return re.sub(r"\s+", " ", _strip_accents(str(value)).strip().lower())


def _norm_key(value):
    """Collapse a key to the form shared by the schema and the spreadsheet.

    ``001``, ``1`` and the spreadsheet's ``1.0`` all collapse to ``1``; ``O``
    and ``IP`` are left alone.
    """
    text = str(value).strip()
    try:
        number = float(text)
    except (ValueError, OverflowError):
        return text.upper()
    if not number.is_integer():
        raise ValueError(f"key {text!r} is not a whole number")
    return str(int(number))


def read_schema_codes(xsd_path):
    """Return ``{catalog: [code, ...]}`` from the catalog schema."""
    with open(xsd_path, encoding="utf-8") as handle:
        content = handle.read()
    codes = {}
    for match in re.finditer(
        r'<xs:simpleType name="([^"]+)">(.*?)</xs:simpleType>', content, re.S
    ):
        name, body = match.group(1), match.group(2)
        values = re.findall(r'<xs:enumeration value="([^"]*)"', body)
        if values:
            codes[name] = values
    return codes


class SheetReader:
    """Read one catalog sheet: metadata block, header row and data rows."""

    def __init__(self, book, sheet):
        self.book = book
        self.sheet = sheet
        self.header_row = self._find_header_row()
        self.columns = [_norm_header(cell.value) for cell in sheet.row(self.header_row)]

    def _find_header_row(self):
        for row in range(self.sheet.nrows):
            if str(self.sheet.cell_value(row, 0)).strip().startswith("c_"):
                return row
        raise ValueError(f"{self.sheet.name}: no header row starting with 'c_'")

    def _date(self, value):
        if isinstance(value, (int, float)) and value:
            return xlrd.xldate_as_datetime(value, self.book.datemode).date().isoformat()
        if isinstance(value, str) and value.strip():
            # SAT writes dates as real Excel dates. Text in a date column means
            # the sheet changed shape, and guessing a format here would ship a
            # wrong validity window; better to stop.
            raise ValueError(
                f"{self.sheet.name}: expected a date, got the text {value.strip()!r}"
            )
        return ""

    def column(self, *candidates):
        for candidate in candidates:
            if candidate in self.columns:
                return self.columns.index(candidate)
        return None

    def metadata(self):
        """Version, revision and publication date declared inside the sheet.

        SAT writes this block differently per sheet -- sometimes as
        "fecha de publicacion", sometimes as "fecha inicio de vigencia" -- so
        the labels are looked up by name in the rows above the header.
        """
        values = {}
        for row in range(self.header_row):
            names = [_norm_header(c.value) for c in self.sheet.row(row)]
            if "version" not in names or row + 1 >= self.header_row:
                continue
            next_cells = self.sheet.row(row + 1)
            for idx, name in enumerate(names):
                if name and idx < len(next_cells):
                    values[name] = next_cells[idx].value
            break

        def text(name):
            # Kept exactly as the sheet shows it: "2.0", "1.1", "A", "0.0".
            return str(values.get(name, "")).strip()

        published = values.get("fecha de publicacion") or values.get(
            "fecha inicio de vigencia"
        )
        return {
            "version": text("version"),
            "revision": text("revision"),
            "publication_date": self._date(published) if published else "",
        }

    def rows(self):
        code_idx = 0
        name_idx = self.column("descripcion")
        if name_idx is None:
            raise ValueError(
                f"{self.sheet.name}: no description column; columns are {self.columns}"
            )
        start_idx = self.column("fecha inicio de vigencia")
        end_idx = self.column("fecha fin de vigencia")
        for row in range(self.header_row + 1, self.sheet.nrows):
            cells = self.sheet.row(row)
            raw_code = str(cells[code_idx].value).strip()
            if not raw_code:
                continue
            record = {
                "raw_code": raw_code,
                "name": str(cells[name_idx].value).strip(),
                "date_start": self._date(cells[start_idx].value)
                if start_idx is not None
                else "",
                "date_end": self._date(cells[end_idx].value)
                if end_idx is not None
                else "",
            }
            extra = {
                header: str(cells[idx].value).strip()
                for idx, header in enumerate(self.columns)
                if header and idx < len(cells)
            }
            yield record, extra


def build_catalog(book, sheet_name, schema_codes, extra_columns):
    reader = SheetReader(book, book.sheet_by_name(sheet_name))
    remaining = {}
    for code in schema_codes:
        norm = _norm_key(code)
        if norm in remaining:
            raise ValueError(
                f"{sheet_name}: schema keys {remaining[norm]!r} and {code!r} are "
                f"indistinguishable once normalised; the match would be ambiguous"
            )
        remaining[norm] = code

    records = []
    for row, extra in reader.rows():
        norm = _norm_key(row["raw_code"])
        code = remaining.pop(norm, None)
        if code is None:
            raise ValueError(
                f"{sheet_name}: key {row['raw_code']!r} is in the spreadsheet "
                f"but not in the schema"
            )
        record = {
            "id": f"{sheet_name.lower()}_{code.lower()}",
            "code": code,
            "name": row["name"],
            "date_start": row["date_start"],
            "date_end": row["date_end"],
        }
        for field, header in extra_columns.items():
            if header not in extra:
                raise ValueError(
                    f"{sheet_name}: no {header!r} column; columns are {reader.columns}"
                )
            record[field] = extra[header]
        records.append(record)

    if remaining:
        raise ValueError(
            f"{sheet_name}: keys {sorted(remaining.values())} are in the schema "
            f"but not in the spreadsheet"
        )
    # Keep the schema order: it is the order SAT publishes.
    order = {code: idx for idx, code in enumerate(schema_codes)}
    records.sort(key=lambda rec: order[rec["code"]])
    return reader.metadata(), records


def write_csv(path, fieldnames, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def update_sat_catalogs(xls_path, xsd_path):
    book = xlrd.open_workbook(xls_path)
    schema = read_schema_codes(xsd_path)

    missing = sorted(set(CATALOGS) - set(schema))
    if missing:
        raise ValueError(f"schema is missing catalogs: {missing}")

    sources = []
    for sheet_name, (model, extra_columns) in sorted(CATALOGS.items()):
        metadata, records = build_catalog(
            book, sheet_name, schema[sheet_name], extra_columns
        )
        fieldnames = ["id", "code", "name", "date_start", "date_end"]
        fieldnames += list(extra_columns)
        write_csv(os.path.join(DATA_DIR, f"{model}.csv"), fieldnames, records)
        sources.append(
            {
                "id": f"source_{sheet_name.lower()}",
                "catalog": sheet_name,
                "model": model,
                "version": metadata["version"],
                "revision": metadata["revision"],
                "publication_date": metadata["publication_date"],
            }
        )
        _logger.info("%s: %s keys -> %s", sheet_name, len(records), model)

    write_csv(
        os.path.join(DATA_DIR, f"{SOURCE_MODEL}.csv"),
        ["id", "catalog", "model", "version", "revision", "publication_date"],
        sources,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xls", help="path to the official catNomina .xls")
    parser.add_argument("xsd", help="path to the official catNomina .xsd")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    update_sat_catalogs(args.xls, args.xsd)


if __name__ == "__main__":
    main()
