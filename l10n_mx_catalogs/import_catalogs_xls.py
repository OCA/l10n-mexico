#!/usr/bin/env python3
import argparse
import csv

import xlrd


def update_sat_catalogs(catalog_file_path):
    # open xml file and parse it
    book = xlrd.open_workbook(catalog_file_path)
    _update_clave_unidad_catalog_csv(book)
    _update_prod_serv_catalog_csv(book)
    _update_codigo_postal_catalog_csv(book)
    _update_tipo_relacion_catalog_csv(book)


def _update_clave_unidad_catalog_csv(book):
    importer = CatalogImporter(
        catalog_name="c_clave_unidad",
        row_mapping={
            "c_ClaveUnidad": "code",
            "Nombre": "name",
            "Descripción": "description",
            "Nota": False,
            "Fecha de inicio de vigencia": False,
            "Fecha de fin de vigencia": False,
            "Símbolo": "symbol",
        },
        key_fields=["c_ClaveUnidad"],
    )

    sheets = importer.get_sheets_with_prefix(book, "c_ClaveUnidad")
    rows = importer.map_rows_to_model(sheets)
    importer.write_to_csv(rows)


def _update_codigo_postal_catalog_csv(book):
    importer = CatalogImporter(
        catalog_name="c_codigo_postal",
        row_mapping={
            "c_CodigoPostal": "code",
            "c_Estado": "state_code",
            "c_Municipio": "municipality_code",
            "c_Localidad": "locality_code",
        },
        key_fields=["c_CodigoPostal"],
    )

    sheets = importer.get_sheets_with_prefix(book, "c_CodigoPostal")
    rows = importer.map_rows_to_model(sheets)

    # validate rows
    def validate_row(rows):
        for row in rows:
            if "c_CodigoPostal" in row["code"]:
                continue
            yield row

    validated_rows = validate_row(rows)
    importer.write_to_csv(validated_rows)


def _update_prod_serv_catalog_csv(book):
    importer = CatalogImporter(
        catalog_name="c_clave_prod_serv",
        row_mapping={
            "c_ClaveProdServ": "code",
            "Descripción": "name",
            "Incluir IVA trasladado": "includes_iva",
            "Incluir IEPS trasladado": "includes_ieps",
            "Complemento que debe incluir": False,
            "FechaInicioVigencia": False,
            "FechaFinVigencia": False,
            "Estímulo Franja Fronteriza": "border_incentive",
            "Palabras similares": "alternative_names",
        },
        key_fields=["c_ClaveProdServ"],
    )

    sheets = importer.get_sheets_with_prefix(book, "c_ClaveProdServ")
    rows = importer.map_rows_to_model(sheets)
    importer.write_to_csv(rows)


def _update_tipo_relacion_catalog_csv(book):
    importer = CatalogImporter(
        catalog_name="c_tipo_relacion",
        row_mapping={
            "c_TipoRelacion": "code",
            "Descripción": "description",
            "FechaInicioVigencia": False,
            "FechaFinVigencia": False,
        },
        key_fields=["c_TipoRelacion"],
    )

    sheets = importer.get_sheets_with_prefix(book, "c_TipoRelacion")
    rows = importer.map_rows_to_model(sheets)
    formatted_rows = apply_zero_fill_on_col(rows, "code", 2)

    importer.write_to_csv(formatted_rows)


def apply_zero_fill_on_col(rows, col, num_zeros):
    for row in rows:
        row[col] = row[col].zfill(num_zeros)
        yield row


class CatalogImporter:
    csv_file_prefix = "data/l10n_mx_catalogs."
    catalog_name: str
    row_mapping: dict
    key_fields: list

    def __init__(self, catalog_name, row_mapping, key_fields):
        self.catalog_name = catalog_name
        self.row_mapping = row_mapping
        self.key_fields = key_fields

    def get_sheets_with_prefix(self, book, prefix):
        prefix = prefix.lower()
        for sheet in book.sheets():
            sheet_name = sheet.name.lower()
            if sheet_name.startswith(prefix):
                yield sheet

    def map_rows_to_model(self, sheets):
        for sheet in sheets:
            header_skip = False
            header_rows = list(self.row_mapping.keys())
            for row_idx in range(sheet.nrows):
                row_data = sheet.row(row_idx)
                if not header_skip:
                    if row_data[0].value == header_rows[0]:
                        header_skip = True
                    continue

                if row_data[0].value != "":
                    yield self._map_row_data(row_data)

    def _map_xls_col_name(self, field_name):
        return list(self.row_mapping.keys()).index(field_name)

    def _map_row_data(self, row_data):
        row = {}
        for col_name, field in self.row_mapping.items():
            if field:
                col_idx = self._map_xls_col_name(col_name)
                value = row_data[col_idx].value
                # remove trailing zeros from float values
                if isinstance(value, float):
                    value = str(value).rstrip("0").rstrip(".")

                row[field] = value

        name = self.catalog_name
        for key in self.key_fields:
            field_name = self.row_mapping[key]
            name += "_%s" % row[field_name]

        row["id"] = name
        return row

    def write_to_csv(self, rows_input):
        with open(self.csv_file_prefix + self.catalog_name + ".csv", "w") as file:
            fieldnames = [field for field in self.row_mapping.values() if field]
            fieldnames.insert(0, "id")
            csvwriter = csv.DictWriter(file, fieldnames)
            csvwriter.writeheader()
            csvwriter.writerows(rows_input)


if __name__ == "__main__":
    # get catalog file path from args
    parser = argparse.ArgumentParser(description="Update SAT catalogs from XLS file.")
    parser.add_argument("catalog_path", type=str, help="SAT catalogs XLS file path")

    args = parser.parse_args()

    if not args.catalog_path:
        raise Exception("No catalog file path provided")

    # Import SAT Catalogs
    update_sat_catalogs(args.catalog_path)
