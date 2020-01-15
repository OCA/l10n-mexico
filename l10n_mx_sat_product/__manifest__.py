# -*- coding: utf-8 -*-

{
    'name': 'l10n_mx_sat_product',
    'version': '0.1',
    'category': 'Hidden',
    'summary': 'Provee la clave del SAT y la unidad de medida del SAT',
    'description': """
""",
    'depends': [
        'base',
        
    ],
    'external_dependencies' : {
        'python' : ['pyOpenSSL'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/product_view.xml',
        
    ],
    
    "post_init_hook": "post_init_hook",
    'installable': True,
    'auto_install': False,
    'uninstall_hook': 'uninstall_hook',
    
}
