# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    "name": "Mexico - SAT CFDI on Purchase Orders",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Create the vendor bill of a purchase order from a CFDI "
    "downloaded from the SAT",
    "author": "Jarsa, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "license": "AGPL-3",
    "depends": ["purchase", "l10n_mx_sat"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/l10n_mx_sat_purchase_invoice_wizard_views.xml",
        "views/l10n_mx_sat_document_views.xml",
        "views/purchase_order_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "development_status": "Alpha",
    "maintainers": ["alan196"],
}
