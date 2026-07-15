# Copyright (C) 2023 Open Source Integrators
# (https://www.opensourceintegrators.com).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
{
    "name": "Mexican Addendum For Invoices For MABE",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "summary": "Mexican Localization Addendum For MABE",
    "author": "Open Source Integrators, Odoo Mexican Association (AMOdoo),"
    " Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "category": "Accounting",
    "depends": ["l10n_mx_cfdi_account", "base_address_extended"],
    "data": [
        "views/account_move_views.xml",
        "views/l10n_mx_addenda_mabe_view.xml",
        "views/res_partner_views.xml",
    ],
    "application": False,
}
