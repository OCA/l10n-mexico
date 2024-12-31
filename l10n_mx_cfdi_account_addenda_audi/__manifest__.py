# Copyright (C) 2023 Open Source Integrators (https://www.opensourceintegrators.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
{
    "name": "Mexican Addendum For Invoices For Audi",
    "version": "17.0.1.3.0",
    "license": "LGPL-3",
    "summary": "Mexican Localization Addendum For Audi",
    "author": "Open Source Integrators, Odoo Mexican Association (AMOdoo)",
    "maintainer": "Open Source Integrators",
    "website": "https://github.com/amxodoo/enterprise",
    "depends": ["account", "l10n_mx_edi", "product"],
    "data": [
        "views/account_move.xml",
        "views/l10n_mx_edi_addenda_audi.xml",
        "views/res_partner_views.xml",
    ],
    "application": False,
}
