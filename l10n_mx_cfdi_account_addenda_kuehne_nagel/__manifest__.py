# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Mexican Addendum For Invoices For Kuehne+Nagel",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "summary": "Mexican Localization Addendum KNRECEPCION For Kuehne+Nagel",
    "author": "Gray Matter Logic, Odoo Mexican Association (AMOdoo),"
    " Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "category": "Accounting",
    "depends": ["l10n_mx_cfdi_account"],
    "data": [
        "views/account_move.xml",
        "views/l10n_mx_cfdi_account_addenda_kuehne_nagel.xml",
    ],
    "application": False,
}
