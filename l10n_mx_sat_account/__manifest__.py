# Copyright (C) 2019 Open Source Integrators
# Copyright (C) 2019 Serpent Consulting Services
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).lgpl.html).
{
    "name": "Maxico SAT Account",
    "summary": """
        This module provides the list of grouping accounts from
        the Mexican tax authority, Servicio de Administración Tributaria (SAT):
    """,
    "version": "13.0.1.0.0",
    "author": "Open Source Integrators, "
    "Serpent Consulting Services Pvt. Ltd., "
    "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/operating-unit",
    "category": "Localization",
    "depends": ["l10n_mx", "l10n_mx_sat_reference"],
    "license": "AGPL-3",
    "data": [
        "security/ir.model.access.csv",
        "data/sat.account.csv",
        "views/sat_account.xml",
    ],
    "installable": True,
    "development_status": "Beta",
    "maintainers": ["max3903"],
}
