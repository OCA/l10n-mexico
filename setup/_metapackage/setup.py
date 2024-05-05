import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo-addons-oca-l10n-mexico",
    description="Meta package for oca-l10n-mexico Odoo addons",
    version=version,
    install_requires=[
        'odoo-addon-l10n_mx_catalogs>=15.0dev,<15.1dev',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 15.0',
    ]
)
