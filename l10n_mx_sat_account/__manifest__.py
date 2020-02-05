# Copyright (C) 2019 Open Source Integrators
# Copyright (C) 2019 Serpent Consulting Services
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).lgpl.html).
{
    "name": "Mexico SAT Account",
    "summary": "Provides the list of SAT accounts to set on your CoA",
    "version": "13.0.1.0.0",
    "author": "Open Source Integrators, "
              "Serpent Consulting Services Pvt. Ltd., "
              "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/operating-unit",
    "category": "Localization",
    "depends": [
        "l10n_mx",
        "l10n_mx_sat_reference"
    ],
    "license": "AGPL-3",
    "data": [
        "security/ir.model.access.csv",
        "data/sat.account.csv",
        "views/sat_account.xml",
    ],
    "development_status": "Beta",
    "maintainers": ["max3903"],
}
