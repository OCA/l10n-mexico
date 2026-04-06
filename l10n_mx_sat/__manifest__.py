# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    "name": "Mexico - Conexion SAT",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Modulo base para conectar Odoo con el SAT usando credenciales FIEL",
    "author": "Open Source Integrators, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "license": "AGPL-3",
    "depends": ["account"],
    "external_dependencies": {"python": ["cfdiclient"]},
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "development_status": "Alpha",
    "maintainers": ["max3903"],
}
