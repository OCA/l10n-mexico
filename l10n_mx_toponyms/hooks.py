# -*- coding: utf-8 -*-

from .models.helper_functions import get_date_int_and_date_udpate
from .models.helper_functions import insert_into_ir_model_data, select_xmlid
from .models.helper_functions import get_create_and_write_date
from openerp import SUPERUSER_ID

import csv
import logging
import os


# Get a logger to work with
_logger = logging.getLogger(__name__)


try:
    from unidecode import unidecode
except ImportError:
    _logger.debug('Cannot `import unidecode`.')

try:
    from openupgradelib.openupgrade import is_module_installed, load_data
except ImportError:
    _logger.debug('Cannot `import openupgradelib`.')


def _load_county_data(cr):
    """
    Load examples into res_country_state_county, we are not using a normal xml
    to accomplish this task due to it is really slow,
    I know surely this is not the best way to do it but who cares :)
    """
    # Read csv from a specific path
    county_csv = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'examples', 'l10n_mx_county.csv',
    )
    with open(county_csv, 'rt') as csvfile:
        examples = csv.reader(csvfile, delimiter=',')
        _ = examples.next()  # noqa: F841
        for item in examples:
            create_date = write_date = get_create_and_write_date()
            date_init = date_update = get_date_int_and_date_udpate()
            fieldId, name, code = item[0], item[1], item[2]
            state_id = item[3].split('.')[1]
            # Get id of the field to update or to create
            values = {'name': fieldId, 'model': 'res.partner.county'}
            xmlid = select_xmlid(cr, values)
            # review if the related state
            # with the county is created
            values = {
                'name': state_id,
                'model': 'res.country.state',
            }
            state_res_id = select_xmlid(cr, values)
            if not state_res_id:
                _logger.warn(
                    'State %s did not find in model res.country.state',
                    state_id,
                )
                continue
            values = {
                'name': name, 'code': code,
                'state_res_id': state_res_id,
                'module': 'l10n_mx_toponyms',
                'write_date': write_date,
                'id': xmlid, 'create_date': create_date,
                'create_uid': SUPERUSER_ID, 'write_uid': SUPERUSER_ID,
            }
            # It's not a new record and
            # it's only necessary updated it
            if xmlid:
                query = """
                UPDATE res_partner_county SET
                name = %(name)s, code = %(code)s,
                state_id = %(state_res_id)s WHERE id = %(id)s
                """
                cr.execute(query, values)
            # It's a new record thus we proceed to create it
            else:
                # First create the new record in res_partner_county
                # table to get the new id and with this
                # value create its register in ir_model_data table
                query = """
                INSERT INTO res_partner_county(
                    create_date, write_date, name, code, state_id,
                    create_uid, write_uid
                )
                VALUES (
                    %(create_date)s, %(write_date)s, %(name)s,
                    %(code)s, %(state_res_id)s, %(create_uid)s,
                    %(write_uid)s
                ) RETURNING id
                """
                cr.execute(query, values)
                new_id = cr.fetchone()[0]
                # Create the related register in ir_model_data
                values.update({
                    'noupdate': True,
                    'name': fieldId,
                    'res_id': new_id,
                    'model': 'res.partner.county',
                    'date_init': date_init,
                    'date_update': date_update,
                })
                insert_into_ir_model_data(cr, values)


def _load_zip_data(cr):
    """
    Load examples into res_zip, we are not using a normal xml
    to accomplish this task due to it is really slow,
    I know surely this is not the best way to do it but who cares ;)
    """
    # Read csv from a specific path
    zip_csv = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'examples', 'l10n_mx_zip.csv',
    )
    with open(zip_csv, 'rt') as csvfile:
        examples = csv.reader(csvfile, delimiter=',')
        _ = examples.next()  # noqa: F841
        for item in examples:
            create_date = write_date = get_create_and_write_date()
            date_init = date_update = get_date_int_and_date_udpate()
            fieldId, name, location_id = item[0], item[1], item[2]
            county_id = item[3]

            # Get id of the field to update or to create
            values = {'name': fieldId, 'model': 'res.zip'}
            xmlid = select_xmlid(cr, values)
            # Update values in order to find location xmlid
            values = {
                'name': location_id and location_id.split('.')[1] or None,
                'model': 'res.location',
            }
            location_res_id = select_xmlid(cr, values)
            values = {
                'name': county_id.split('.')[1],
                'model': 'res.partner.county',
            }
            county_res_id = select_xmlid(cr, values)
            if not county_res_id:
                _logger.warn(
                    'name %s did not find in model ir_model_data',
                    county_id.split('.')[1],
                )
                continue
            values = {
                'name': name,
                'location_id': location_res_id,
                'county_id': county_res_id,
                'id': xmlid,
                'create_date': create_date,
                'write_uid': SUPERUSER_ID,
                'write_date': write_date,
                'create_uid': SUPERUSER_ID,
                'module': 'l10n_mx_toponyms',
            }
            # It's not a new record and
            # it's only necessary updated it
            if xmlid:
                query = """
                UPDATE res_zip SET
                name = %(name)s, county_id = %(county_id)s
                """
                if location_id:
                    query += ', location_id = %(location_id)s'
                query += ' WHERE id = %(id)s'
                cr.execute(query, values)
                # It's a new record thus we proceed to create it
            else:
                # First create the new record in res_zip
                # table to get the new id and with the new id
                # create a new register in ir_model_data table
                query = """
                    INSERT INTO res_zip(
                        create_date, write_date, create_uid,
                        write_uid, name, county_id, location_id
                    )
                    VALUES (
                        %(create_date)s, %(write_date)s,
                        %(create_uid)s,  %(write_uid)s,
                        %(name)s, %(county_id)s, %(location_id)s
                    ) RETURNING id
                """
                cr.execute(query, values)
                new_id = cr.fetchone()[0]
                # Create the related register in ir_model_data
                values.update({
                    'noupdate': True,
                    'name': fieldId,
                    'res_id': new_id,
                    'model': 'res.zip',
                    'date_init': date_init,
                    'date_update': date_update,
                })
                insert_into_ir_model_data(cr, values)


def _load_neighborhood_data(cr):
    """
    Load examples into res_neighborhood, we are not using a normal xml
    to accomplish this task due to it is really slow,
    and we have over 150,000 registers to load.
    """
    # Read csv from a specific path
    neighborhood_csv = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'examples', 'l10n_mx_neighborhood.csv',
    )
    with open(neighborhood_csv, 'rt') as csvfile:
        examples = csv.reader(csvfile, delimiter=',')
        _ = examples.next()  # noqa: F841
        for item in examples:
            create_date = write_date = get_create_and_write_date()
            date_init = date_update = get_date_int_and_date_udpate()
            fieldId, code, zip_id = item[0], item[1], item[2]
            name = item[3]
            # Get id of the field to update or to create
            values = {'name': fieldId, 'model': 'res.neighborhood'}
            xmlid = select_xmlid(cr, values)
            # review if the related zip
            # with the neighborhood is created
            values = {'name': zip_id, 'model': 'res.zip'}
            zip_res_id = select_xmlid(cr, values)
            if not zip_res_id:
                _logger.warn(
                    'zip_id %s did not find '
                    'in model ir_model_data',
                    zip_id,
                )
                continue
            values = {
                'name': name, 'code': code,
                'zip_res_id': zip_res_id,
                'module': 'l10n_mx_toponyms',
                'id': xmlid, 'create_date': create_date,
                'create_uid': SUPERUSER_ID, 'write_uid': SUPERUSER_ID,
                'write_date': write_date,
            }
            # It's not a new record and
            # it's only necessary updated it
            if xmlid:
                query = """
                UPDATE res_neighborhood SET
                name = %(name)s, zip_id = %(zip_res_id)s,
                code = %(code)s
                WHERE id = %(id)s
                """
                cr.execute(query, values)
            # It's a new record thus we proceed to create it
            else:
                # First create the new record in
                # res_country_state_county table to get the new id
                # and with this value create its register in
                # ir_model_data table
                query = """
                INSERT INTO res_neighborhood(
                    name, code, zip_id, create_date, write_date,
                    create_uid, write_uid
                )
                VALUES (
                    %(name)s, %(code)s, %(zip_res_id)s,
                    %(create_date)s, %(write_date)s,
                    %(create_uid)s, %(write_uid)s
                ) RETURNING id
                """
                cr.execute(query, values)
                new_id = cr.fetchone()[0]
                # Create the related register in ir_model_data
                values.update({
                    'noupdate': True,
                    'name': fieldId,
                    'res_id': new_id,
                    'model': 'res.neighborhood',
                    'date_init': date_init,
                    'date_update': date_update,
                })
                insert_into_ir_model_data(cr, values)


def _load_l10n_mx_states(cr):
    """
    Update ir_model_data to prevent duplicated values
    there are already loaded catalogs for states and cities from
    l10n_mx_states and l10n_mx_cities respectively, but this module
    will deprecate the other l10n_mx_states and l10n_mx_cities
    """
    if is_module_installed(cr, 'l10n_mx_states'):
        query = """
        UPDATE ir_model_data
        SET module = 'l10n_mx_toponyms'
        WHERE module = 'l10n_mx_states'
        """
        cr.execute(query)
    else:
        filename = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'examples', 'l10n_mx_estados.xml',
        )
        load_data(cr, 'l10n_mx_toponyms', filename)


def _update_res_partner(cr, registry):
    """
    Function use to update the existing loaded data
    in the deprecated modules l10n_mx_states and l10n_mx_cities
    cities, l10n_mx_partner_address
    this funcion will be called only once
    """
    res_zip_obj = registry['res.zip']
    res_neighborhood_obj = registry['res.neighborhood']
    res_partner_obj = registry['res.partner']
    ir_module_obj = registry['ir.module.module']
    partner_adress_module_id = ir_module_obj.search(
        cr, SUPERUSER_ID,
        [('name', '=', 'l10n_mx_partner_address')],
    )[0]
    partner_adress_module = ir_module_obj.browse(
        cr, SUPERUSER_ID, partner_adress_module_id,
    )
    if partner_adress_module.state != 'installed':
        return
    neighborhood_id = None
    # Get all existing partners
    res_partners_ids = res_partner_obj.search(cr, SUPERUSER_ID, [])
    for res_partner in res_partner_obj.browse(
            cr, SUPERUSER_ID, res_partners_ids,):
        if not res_partner.zip:
            continue
        res_zip_ids = res_zip_obj.search(
            cr, SUPERUSER_ID,
            [('code', '=', res_partner.zip.strip())],
        )
        if not res_zip_ids:
            # Print a warning in log
            _logger.warn(
                'Zip %s was not find for the '
                'partner id %s',
                res_partner.zip, res_partner.id,
            )
            continue
        res_zip = res_zip_obj.browse(
            cr, SUPERUSER_ID,
            res_zip_ids[0],
        )
        zip_id = res_zip.id
        location_id = (
            res_zip.location_id.id if
            res_zip.location_id else None,
        )
        county_id = res_zip.county_id.id
        state_id = res_zip.county_id.state_id.id
        num_ext = res_partner.l10n_mx_street3
        num_int = res_partner.l10n_mx_street4
        # Search for neighborhoods
        if res_partner.street2:
            neighborhoods_ids = res_neighborhood_obj.search(
                cr, SUPERUSER_ID,
                [('zip_id', '=', zip_id)],
            )
            for neighborhood in res_neighborhood_obj.browse(
                    cr, SUPERUSER_ID, neighborhoods_ids,):
                if (unidecode(
                        res_partner.street2.lower().replace(' ', ''),) in
                        unidecode(
                            neighborhood.name.lower().replace(' ', ''),),):
                    neighborhood_id = neighborhood.id
                    break
            if not neighborhood_id:
                # Print a warning in log
                _logger.warn(
                    'Neighborhood %s was '
                    'not find for the partner id %s ',
                    unidecode(res_partner.street2),
                    res_partner.id,
                )
        # Write values in partner
        res_partner_obj.write(
            cr, SUPERUSER_ID, res_partner.id, {
                'location_id': location_id, 'county_id': county_id,
                'state_id': state_id, 'num_ext': num_ext,
                'num_int': num_int, 'neighborhood_id': neighborhood_id,
                'zip_id': zip_id,
            },
        )


def _load_localidad_data(cr):
    filename = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'examples', 'l10n_mx_localidad.xml',
    )
    load_data(cr, 'l10n_mx_toponyms', filename)


def post_init_hook(cr, registry):
    _load_l10n_mx_states(cr)
    _load_county_data(cr)
    _load_localidad_data(cr)
    _load_zip_data(cr)
    _load_neighborhood_data(cr)
    _update_res_partner(cr, registry)
