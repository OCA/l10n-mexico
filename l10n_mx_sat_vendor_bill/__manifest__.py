# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    "name": "Mexico - SAT Vendor Bill Download",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Download vendor bills (CFDIs recibidos) from SAT via Descarga Masiva",
    "author": "Open Source Integrators, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "license": "AGPL-3",
    "depends": ["l10n_mx_sat", "l10n_mx"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/l10n_mx_sat_download_request_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "development_status": "Alpha",
    "maintainers": ["max3903"],
}
