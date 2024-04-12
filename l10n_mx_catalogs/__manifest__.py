{
    "name": "Catálogos SAT para localización mexicana",
    "summary": """
        Catálogos del Servicio de Administración Tributaria de México
        """,
    "description": """
        Catálogos del SAT
    """,
    "author": "Alexis López Zubieta <alexis.lopez@augetec.com> (Auge TEC)",
    "website": "https://github.com/OCA/l10n-mexico",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    "category": "Localization",
    "version": "15.0.1.0.2",
    "license": "LGPL-3",
    # any module necessary for this one to work correctly
    "depends": ["base", "l10n_mx"],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        # 'views/views.xml',
        # 'views/templates.xml',
        # SAT catalogs
        "data/l10n_mx_catalogs.c_clave_unidad.csv",
        "data/l10n_mx_catalogs.c_clave_prod_serv.csv",
        "data/l10n_mx_catalogs.c_codigo_postal.csv",
        # 'data/l10n_mx_catalogs.c_colonia.csv',
        "data/l10n_mx_catalogs.c_config_autotransporte.csv",
        "data/l10n_mx_catalogs.c_figura_transporte.csv",
        "data/l10n_mx_catalogs.c_forma_pago.csv",
        "data/l10n_mx_catalogs.c_localidad.csv",
        "data/l10n_mx_catalogs.c_meses.csv",
        "data/l10n_mx_catalogs.c_metodo_pago.csv",
        "data/l10n_mx_catalogs.c_motivo_cancelacion.csv",
        "data/l10n_mx_catalogs.c_pais.csv",
        "data/l10n_mx_catalogs.c_parte_transporte.csv",
        "data/l10n_mx_catalogs.c_periodicidad.csv",
        "data/l10n_mx_catalogs.c_regimen_fiscal.csv",
        "data/l10n_mx_catalogs.c_sub_tipo_rem.csv",
        "data/l10n_mx_catalogs.c_tipo_permiso.csv",
        "data/l10n_mx_catalogs.c_tipo_relacion.csv",
        "data/l10n_mx_catalogs.c_uso_cfdi.csv",
    ],
    # only loaded in demonstration mode
    "demo": [
        "demo/demo.xml",
    ],
}
