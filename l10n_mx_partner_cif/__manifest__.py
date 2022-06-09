# Copyright 2022 Jarsa
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Mexico Partner CIF Import",
    "version": "15.0.1.0.0",
    "author": ("Jarsa," "Odoo Community Association (OCA)"),
    "category": "Accounting/Localizations",
    "website": "https://github.com/OCA/l10n-mexico",
    "depends": ["l10n_mx_toponym", "l10n_mx_partner"],
    "installable": True,
    "license": "AGPL-3",
    "data": [
        "views/res_partner_view.xml",
    ],
    "external_dependencies": {
        "python": ["opencv-python", "pdf2image", "pytesseract"],
    },
}
