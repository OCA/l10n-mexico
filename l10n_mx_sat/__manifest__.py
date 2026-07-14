# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    "name": "Mexico - SAT Connection",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Connect to the SAT portal using FIEL credentials & manage downloads",
    "author": (
        "Gray Matter Logic, Asociacion Mexicana de Odoo (AMOdoo), "
        "Odoo Community Association (OCA), Cloud Lotus"
    ),
    "website": "https://github.com/OCA/l10n-mexico",
    "license": "AGPL-3",
    "depends": ["base"],
    "external_dependencies": {
        "python": ["satcfdi"],
    },
    "data": [
        "security/l10n_mx_sat_security.xml",
        "security/ir.model.access.csv",
        "security/l10n_mx_sat_rules.xml",
        "data/ir_cron_data.xml",
        "wizards/l10n_mx_sat_fiel_credentials_wizard_views.xml",
        "views/res_company_views.xml",
        "views/l10n_mx_sat_document_views.xml",
        "views/l10n_mx_sat_download_request_views.xml",
    ],
    "installable": True,
    "development_status": "Alpha",
    "maintainers": ["max3903"],
}
