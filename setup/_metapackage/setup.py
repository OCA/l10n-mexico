import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo13-addons-oca-l10n-mexico",
    description="Meta package for oca-l10n-mexico Odoo addons",
    version=version,
    install_requires=[
        'odoo13-addon-l10n_mx_res_partner',
        'odoo13-addon-l10n_mx_sat_account',
        'odoo13-addon-l10n_mx_sat_reference',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
    ]
)
