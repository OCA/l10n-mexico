{
    "name": "CFDI Carta Porte - Inventarios",
    "summary": (
        "Provee soporte para generación de cartas porte "
        "con gestión de flotas simplificada."
    ),
    "author": "Alexis López Zubieta <alexis.lopez@augetec.com> (Auge TEC), "
    "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "license": "LGPL-3",
    "category": "Stock",
    "version": "19.0.1.1.0",
    "depends": [
        "base",
        "base_geolocalize",
        "base_address_extended",
        "stock",
        "l10n_mx_cfdi_account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "views/inventory_transfer_cfdi_view.xml",
        "views/view_partner_form_inherit.xml",
        "views/cfdi_transporter_view.xml",
        "views/cfdi_vehicle_view.xml",
        "views/waybill_view.xml",
        "views/stock_location_form_inherit.xml",
        "views/product_template.xml",
        "reports/waybill_report.xml",
    ],
    "demo": [
        "demo/res_partner.xml",
        "demo/product_template.xml",
        "demo/cfdi_transporter.xml",
        "demo/cfdi_vehicle_trailer.xml",
        "demo/cfdi_vehicle.xml",
        "demo/waybill.xml",
        "demo/waybill_entry.xml",
    ],
}
