# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging
from contextlib import closing
from os.path import join, dirname, realpath
from lxml import etree, objectify

from werkzeug import url_quote

from odoo import api, tools, SUPERUSER_ID
import requests

_logger = logging.getLogger(__name__)


def post_init_hook(cr, registry):
    _load_product_sat_catalog(cr, registry)
    _assign_codes_uom(cr, registry)
    

def uninstall_hook(cr, registry):
    cr.execute("DELETE FROM l10n_mx_edt_product_sat_code;")
    cr.execute("DELETE FROM ir_model_data WHERE model='l10n_mx_edt.product.sat.code';")

def _load_product_sat_catalog(cr, registry):
    """Import CSV data as it is faster than xml and because we can't use
    noupdate anymore with csv"""
    csv_path = join(dirname(realpath(__file__)), 'data',
                    'l10n_mx_edt.product.sat.code.csv')
    csv_file = open(csv_path, 'rb')
    cr.copy_expert(
        """COPY l10n_mx_edt_product_sat_code(code, name, applies_to, active)
           FROM STDIN WITH DELIMITER '|'""", csv_file)
    # Create xml_id, to allow make reference to this data
    cr.execute(
        """INSERT INTO ir_model_data
           (name, res_id, module, model, noupdate)
           SELECT concat('prod_code_sat_', code), id, 'l10n_mx_edt', 'l10n_mx_edt.product.sat.code', true
           FROM l10n_mx_edt_product_sat_code """)


def _assign_codes_uom(cr, registry):
    """Assign the codes in UoM of each data, this is here because the data is
    created in the last method"""
    tools.convert.convert_file(
        cr, 'l10n_mx_sat_product', 'data/product_data.xml', None, mode='init',
        kind='data')



