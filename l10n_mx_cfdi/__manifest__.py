# -*- coding: utf-8 -*-
{
    "name": "l10n_mx_cfdi",
    "summary": """Base module for CFDI compliance in Mexico""",
    "description": """
        This module provides the base for CFDI compliance in Mexico.
        Which includes:
        * CFDI Catalogs Models
        * CFDI Catalogs Data Import Wizard
    """,
    "author": "Auge Tec, Odoo Community Association (OCA)",
    "maintainers": ["azubieta"],
    "website": "https://github.com/OCA/l10n-mexico",
    "category": "Invoicing Management",
    "license": "AGPL-3",
    "version": "15.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": ["base", "mail"],
    # always loaded
    "data": [
        "security/access_groups.xml",
        "security/ir.model.access.csv",
        "views/views.xml",
        "wizards/cfdi_document_import_wizard_views.xml",
    ],
    "external_dependencies": {
        "python": ["simple-cfdi"],
    },
}
