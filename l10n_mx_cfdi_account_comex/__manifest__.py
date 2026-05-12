{
    'name': "Mexico foreign trade invoicing compliance",
    'summary': "Mexico foreign trade invoicing compliance",
    'description': """""",
    'author': "Alexis López Zubieta <alexis.lopez@augetec.com> (Auge TEC), "
              "Odoo Community Association (OCA)",
    'website': "https://augetec.com",
    'category': 'Localization',
    'version': '19.0.0.0.1',
    'license': 'GPL-3',
    'depends': ['base', 'l10n_mx_cfdi_account', 'l10n_mx_cfdi_catalogs_comex'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
}
