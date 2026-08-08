{
    "name": "Mexican income tax withholding on salaries",
    "summary": "ISR tariffs and employment subsidy, dated, with the calculation",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "category": "Localization",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "installable": True,
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "data/l10n_mx.uma.csv",
        "data/l10n_mx.employment.subsidy.csv",
        "data/l10n_mx.isr.tariff.csv",
        "data/l10n_mx.isr.tariff.line.csv",
    ],
}
