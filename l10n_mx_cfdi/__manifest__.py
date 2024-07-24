{
    "name": "Mexico - Electronic Invoicing",
    "summary": "Allow generating CFDI (Comprobante Fiscal Digital por Internet)",
    "author": "Alexis López Zubieta <alexis.lopez@augetec.com> (Auge TEC), "
    "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "license": "LGPL-3",
    "category": "Accounting",
    "version": "17.0.1.0.0",
    "depends": ["account", "l10n_mx_catalogs"],
    "external_dependencies": {
        "python": ["facturama"],
    },
    "data": [
        "security/ir.model.access.csv",
        "security/l10n_mx_cfdi_security.xml",

        "data/cfdi_publico_en_general.xml",
        "data/paper_format.xml",

        "views/cfdi_document.xml",
        "views/cfdi_documents_issued.xml",
        "views/cfdi_issuer.xml",
        "views/cfdi_menu.xml",
        "views/cfdi_series.xml",
        "views/cfdi_service.xml",
        "views/product_template.xml",
        "views/res_partner.xml",

        "reports/report_cfdi_blocks.xml",
    ],
}
