# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Mexico - Financial Reports",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "countries": ["mx"],
    "summary": "Financial and tax reports for the Mexican localization",
    "author": "Gray Matter Logic, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "license": "AGPL-3",
    "depends": [
        "account_usability",
        "l10n_mx",
        "mis_builder",
    ],
    "data": [
        "data/mis.report.style.csv",
        "data/mis.report.csv",
        "data/mis.report.kpi.csv",
        "data/mis.report.instance.csv",
        "data/mis.report.instance.period.csv",
        "security/ir.model.access.csv",
        "wizards/l10n_mx_financial_report_wizard_views.xml",
        "views/l10n_mx_report_menu.xml",
        "report/l10n_mx_financial_report_templates.xml",
    ],
    "installable": True,
    "development_status": "Alpha",
    "maintainers": ["max3903"],
}
