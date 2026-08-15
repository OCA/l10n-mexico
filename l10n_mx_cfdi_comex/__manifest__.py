{
    "name": "Mexico foreign trade invoicing compliance",
    "summary": "Mexico foreign trade invoicing compliance",
    "author": "Alexis López Zubieta <alexis.lopez@augetec.com> (Auge TEC), "
    "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "category": "Localization",
    "version": "19.0.1.1.0",
    "license": "GPL-3",
    "depends": [
        "base",
        "account",
        "sale",
        "sale_stock",
        "stock_landed_costs",
        "l10n_mx_cfdi_account",
        "l10n_mx_catalogs_comex",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/pedimento_views.xml",
        "views/product_template_views.xml",
        "views/stock_landed_cost_views.xml",
        "views/stock_lot_views.xml",
        "views/account_move_views.xml",
    ],
    "demo": [
        "demo/pedimento.xml",
        "demo/product_template.xml",
        "demo/stock_lot.xml",
        "demo/stock_landed_cost.xml",
    ],
}
