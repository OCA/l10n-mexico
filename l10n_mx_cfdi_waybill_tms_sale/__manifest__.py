# Copyright (C) 2026 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "CFDI Carta Porte - Transport Invoice",
    "summary": "Add the trip Carta Porte to the freight invoice",
    "version": "19.0.1.0.0",
    "license": "AGPL-3",
    "category": "Localization",
    "author": "Open Source Integrators, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "depends": [
        "l10n_mx_cfdi_waybill_tms",
        "tms_sale",
        "l10n_mx_cfdi_account",
    ],
    "data": [
        "views/account_move.xml",
    ],
    "demo": [
        "demo/account_move.xml",
    ],
    "development_status": "Alpha",
    "maintainers": ["max3903"],
}
