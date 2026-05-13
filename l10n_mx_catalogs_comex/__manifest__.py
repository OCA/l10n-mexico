{
    'name': "Mexico Foreign Trade Catalogs",
    'summary': "Foreign trade catalogs for Mexico",
    'description': """""",
    'author': "Alexis López Zubieta <alexis.lopez@augetec.com> (Auge TEC), "
              "Odoo Community Association (OCA)",
    'website': "https://augetec.com",
    'category': 'Localization',
    'version': '19.0.0.0.1',
    'license': 'GPL-3',
    'depends': ['base'],
    'data': [
        'data/l10n_mx_catalogs.c_aduana.csv',
        'data/l10n_mx_catalogs.c_fraccion.csv',
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
}
