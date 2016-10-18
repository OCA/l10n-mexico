# -*- coding: utf-8 -*-
##############################################################################
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see http://www.gnu.org/licenses/.
#
##############################################################################

{
    'name': 'Toponyms Mexico',
    'version': '1.0.0',
    'author': 'OpenPyme',
    'category': 'Localization',
    'website': 'http://www.openpyme.mx',
    'license': 'GPL-3',
    'depends': [
        'l10n_mx',
        'purchase',
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
