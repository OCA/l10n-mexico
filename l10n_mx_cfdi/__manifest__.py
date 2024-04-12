# -*- coding: utf-8 -*-
{
    "name": "CFDI Mexico - Facturación",
    "summary": """
        Allow generating CFDI (Comprobante Fiscal Digital por Internet) for Mexico.""",
    "description": """
        Allow generating CFDI (Comprobante Fiscal Digital por Internet) for Mexico.
    """,
    "author": "Alexis López Zubieta <alexis.lopez@augetec.com> (Auge TEC)",
    "website": "https://www.augecrm.com",
    "license": "LGPL-3",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Accounting",
    "version": "15.0.1.0.4",
    # any module necessary for this one to work correctly
    "depends": ["base", "account", "l10n_mx", "l10n_mx_catalogs"],
    # always loaded
    "data": [
        # security rules
        "security/ir.model.access.csv",
        "security/l10n_mx_cfdi_security.xml",
        # presets
        "data/cfdi_publico_en_general.xml",  # references l10n_mx_cfdi.regimen_fiscal therefore must be loaded after it
        "data/paper_format.xml",  # references l10n_mx_cfdi.regimen_fiscal therefore must be loaded after it
        # inherited views
        "views/inherit/account_view_move_form.xml",
        "views/inherit/account_view_out_invoice_tree.xml",
        "views/inherit/base_view_partner_form.xml",
        "views/inherit/product_product_template_form_view.xml",
        "views/inherit/account_view_account_payment_register_form.xml",
        "views/inherit/account_view_account_payment_form.xml",
        "views/inherit/res_config_settings_views.xml",
        # new views
        "views/cfdi_menu.xml",
        "views/cfdi_series_view.xml",
        "views/cfdi_issuer_view.xml",
        "views/cfdi_service_view.xml",
        "views/cfdi_document_view.xml",
        "views/cfdi_documents_issued_view.xml",
        "wizard/document_cancel_form.xml",
        "wizard/create_cfdi_publico_en_general.xml",
        "wizard/account_invoice_send_views.xml",
        "wizard/download_cfdi_files_wizard.xml",
        "reports/report_cfdi_blocks.xml",
        "reports/report_external_layouts.xml",
        "reports/report_invoice.xml",
        "reports/report_payment.xml",
    ],
    # only loaded in demonstration mode
    "demo": [
        "demo/demo.xml",
    ],
    "external_dependencies": {
        "python": ["facturama"],
    },
}
