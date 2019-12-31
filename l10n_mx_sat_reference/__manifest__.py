# Copyright (C) 2019 Open Source Integrators
# Copyright (C) 2019 Serpent Consulting Services
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).lgpl.html).
{
    "name": "Maxico SAT Reference",
    "summary": """
        This module provides the list of references to documents that
        the Mexican tax authority, Servicio de Administración Tributaria
        (SAT) requires to be signed/transferred.
    """,
    "version": "12.0.1.0.0",
    "author": "Open Source Integrators, "
              "Serpent Consulting Services Pvt. Ltd., "
              "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/operating-unit",
    "category": "Localization",
    "depends": ["base"],
    "license": "AGPL-3",
    "data": [
        "security/ir.model.access.csv",
        "views/sat_receipt_type_view.xml",
        "views/sat_receipt_use_view.xml",
        "views/sat_relation_type_view.xml",
        "data/sat.receipt.type.csv",
        "data/sat.receipt.use.csv",
        "data/sat.relation.type.csv"
    ],
    'installable': True,
    'development_status': 'Beta',
    'maintainers': [
        'max3903',
    ],
}
