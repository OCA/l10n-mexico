# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    "name": "Mexico - SAT Connection",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Connect with the SAT using the Electronic Signature (FIEL) credentials",
    "author": "Open Source Integrators, "
    "Asociacion Mexicana de Odoo (AMOdoo), "
    "Odoo Community Association (OCA)",
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
