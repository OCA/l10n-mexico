# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import csv
from os.path import dirname, join, realpath

from odoo import SUPERUSER_ID, api


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    mx_country = env["res.country"].search([("code", "=", "MX")])

    # ==== Load res.city ====

    res_city_vals_list = []
    if not env["res.city"].search_count([("country_id", "=", mx_country.id)]):
        csv_path = join(dirname(realpath(__file__)), "static/data", "res.city.csv")
        with open(csv_path, "r") as csv_file:
            for row in csv.DictReader(
                csv_file,
                delimiter="|",
                fieldnames=["l10n_mx_edi_code", "name", "state_xml_id"],
            ):
                state = env.ref(
                    "base.%s" % row["state_xml_id"], raise_if_not_found=False
                )
                res_city_vals_list.append(
                    {
                        "l10n_mx_edi_code": row["l10n_mx_edi_code"],
                        "name": row["name"],
                        "state_id": state.id if state else False,
                        "country_id": mx_country.id,
                    }
                )

    cities = env["res.city"].create(res_city_vals_list)

    if cities:
        cr.execute(
            """
           INSERT INTO ir_model_data (name, res_id, module, model, noupdate)
               SELECT
                    'res_city_mx_' || lower(res_country_state.code) ||
                        '_' || res_city.l10n_mx_edi_code,
                    res_city.id,
                    'l10n_mx_toponym',
                    'res.city',
                    TRUE
               FROM res_city
               JOIN res_country_state ON res_country_state.id = res_city.state_id
               WHERE res_city.id IN %s
        """,
            [tuple(cities.ids)],
        )

    # ==== Load l10n_mx_edi.res.locality ====

    locality_vals_list = []
    if not env["l10n_mx_edi.res.locality"].search_count([]):
        csv_path = join(
            dirname(realpath(__file__)), "static/data", "l10n_mx_edi.res.locality.csv"
        )
        with open(csv_path, "r") as csv_file:
            for row in csv.DictReader(
                csv_file, delimiter="|", fieldnames=["code", "name", "state_xml_id"]
            ):
                state = env.ref(
                    "base.%s" % row["state_xml_id"], raise_if_not_found=False
                )
                locality_vals_list.append(
                    {
                        "code": row["code"],
                        "name": row["name"],
                        "state_id": state.id if state else False,
                        "country_id": mx_country.id,
                    }
                )

        localities = env["l10n_mx_edi.res.locality"].create(locality_vals_list)

        if localities:
            cr.execute(
                """
               INSERT INTO ir_model_data (name, res_id, module, model, noupdate)
                   SELECT
                        'res_locality_mx_' || lower(res_country_state.code) || '_' ||
                            l10n_mx_edi_res_locality.code,
                        l10n_mx_edi_res_locality.id,
                        'l10n_mx_toponym',
                        'l10n_mx_edi.res.locality',
                        TRUE
                   FROM l10n_mx_edi_res_locality
                   JOIN res_country_state ON
                    res_country_state.id = l10n_mx_edi_res_locality.state_id
                   WHERE l10n_mx_edi_res_locality.id IN %s
            """,
                [tuple(localities.ids)],
            )

    # ==== Load res.city.zip ====

    city_vals_list = []
    if not env["res.city.zip"].search_count([("country_id", "=", mx_country.id)]):
        csv_path = join(dirname(realpath(__file__)), "static/data", "res.city.zip.csv")
        with open(csv_path, "r") as csv_file:
            for row in csv.DictReader(
                csv_file,
                delimiter="|",
                fieldnames=[
                    "l10n_mx_edi_colony_code",
                    "name",
                    "l10n_mx_edi_colony",
                    "city_xml_id",
                    "locality_xml_id",
                ],
            ):
                city = env.ref(
                    "l10n_mx_toponym.%s" % row["city_xml_id"], raise_if_not_found=False
                )
                locality = env.ref(
                    "l10n_mx_toponym.%s" % row["locality_xml_id"],
                    raise_if_not_found=False,
                )
                city_vals_list.append(
                    {
                        "l10n_mx_edi_colony_code": row["l10n_mx_edi_colony_code"],
                        "name": row["name"],
                        "l10n_mx_edi_colony": row["l10n_mx_edi_colony"],
                        "city_id": city.id if city else False,
                        "l10n_mx_edi_locality_id": locality.id if locality else False,
                    }
                )

        cities = env["res.city.zip"].create(city_vals_list)

        if cities:
            cr.execute(
                """
               INSERT INTO ir_model_data (name, res_id, module, model, noupdate)
                   SELECT
                        'res_city_zip_mx_' || lower(res_country_state.code) || '_' ||
                            res_city.l10n_mx_edi_code || '_' ||
                            res_city_zip.l10n_mx_edi_colony_code || '_' ||
                            res_city_zip.name,
                        res_city_zip.id,
                        'l10n_mx_toponym',
                        'res.city.zip',
                        TRUE
                   FROM res_city_zip
                   JOIN res_city ON res_city.id = res_city_zip.city_id
                   JOIN res_country_state ON res_country_state.id = res_city.state_id
                   WHERE res_city_zip.id IN %s
            """,
                [tuple(cities.ids)],
            )
