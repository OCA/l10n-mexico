{
    "name": "HR Expense Vendor Bill",
    "summary": "Create vendor bills from employee expenses paid on own account",
    "author": "OSI, AMOdoo, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-mexico",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "depends": ["account", "hr_expense", "base"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/hr_expense_views.xml",
        "views/account_move_views.xml",
        "views/hr_expense_sheet_inherit_views.xml",
    ],
    "demo": [
        "demo/res_company_demo.xml",
        "demo/res_partner_demo.xml",
        "demo/hr_expense_demo.xml",
    ],
    "installable": True,
    "application": False,
    "license": "AGPL-3",
}
