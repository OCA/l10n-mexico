# Copyright (C) 2023 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Contact CSF for Mexico",
    "summary": "Validate the VAT",
    "version": "16.0.1.0.1",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/l10n-mexico",
    "author": "Open Source Integrators, " "Odoo Community Association (OCA)",
    "category": "Localization",
    "depends": ["contacts"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/import_csf.xml",
        "views/res_partner_view.xml",
    ],
    "external_dependencies": {
        "python": ["pdfminer.six==20220319"],
    },
}
