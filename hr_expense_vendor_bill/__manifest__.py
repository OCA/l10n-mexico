{
    "name": "HR Expense Vendor Bill",
    "summary": "Genera automáticamente facturas de proveedor a partir de gastos de empleados",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "depends": ["account", "hr_expense", "base"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/hr_expense_views.xml",
        "views/account_move_views.xml",
        "views/hr_expense_sheet_inherit_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "AGPL-3",
}
