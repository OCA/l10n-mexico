# -*- coding: utf-8 -*-
# Copyright 2016 OpenPyme
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import datetime

import logging

# Get a logger to work with
_logger = logging.getLogger(__name__)


def select_xmlid(cr, data):
    query = """
    SELECT res_id FROM ir_model_data
    WHERE name = %(name)s and
    model = %(model)s
    """
    cr.execute(query, data)
    result = cr.fetchone()
    xmlid = result[0] if result else None
    return xmlid


def insert_into_ir_model_data(cr, data):
    query = """
    INSERT INTO ir_model_data(
        create_date, write_date, write_uid, noupdate, name,
        module, model, res_id, date_init, date_update,
        create_uid
    )
    VALUES (
       %(create_date)s, %(write_date)s, %(write_uid)s,
       %(noupdate)s, %(name)s, %(module)s, %(model)s,
       %(res_id)s, %(date_init)s, %(date_update)s,
       %(create_uid)s
    )
    """
    _logger.debug(query, data)
    cr.execute(query, data)


def get_create_and_write_date():
    date_and_time = datetime.strftime(
        datetime.now(),
        '%Y-%m-%d %H:%M:%S.%f',
    )
    return date_and_time


def get_date_int_and_date_udpate():
    date_and_time = datetime.strftime(
        datetime.now(),
        '%Y-%m-%d %H:%M:%S',
    )
    return date_and_time
