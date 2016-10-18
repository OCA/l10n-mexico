# -*- coding: utf-8 -*-
# Copyright 2016 OpenPyme
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Toponyms Mexico',
    'version': '9.0.1.0.0',
    'author': 'OpenPyme, Odoo Community Association (OCA)',
    'category': 'Localization',
    'website': 'http://www.openpyme.mx',
    'license': 'AGPL-3',
    'depends': [
        'l10n_mx',
    ],
    # The order here is really important
    # Be careful before changing it
    'data': [
        'views/res_county.xml',
        'views/res_localidad.xml',
        'views/res_partner.xml',
        'views/res_zip.xml',
        'views/res_neighborhood.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'external_dependencies': {
        'python': [
            'unidecode',
        ],
    },
    'installable': True,
}
