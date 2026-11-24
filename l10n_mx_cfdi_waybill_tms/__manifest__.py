# Copyright (C) 2026 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "CFDI Carta Porte - Transport",
    "summary": "Stamp a Mexican Carta Porte from a cargo trip",
    "version": "19.0.1.1.0",
    "license": "AGPL-3",
    "category": "Localization",
    "author": "Open Source Integrators, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "depends": ["tms", "l10n_mx_cfdi_waybill"],
    "data": [
        "security/ir.model.access.csv",
        "views/fleet_vehicle.xml",
        "views/tms_driver.xml",
        "views/tms_order.xml",
        "views/waybill.xml",
        "views/res_config_settings.xml",
    ],
    "demo": [
        "demo/tms_order.xml",
    ],
    "development_status": "Alpha",
    "maintainers": ["max3903"],
}
