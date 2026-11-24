from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Issuers of PACs without a registration step only need their local CSD."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    issuers = env["l10n_mx_cfdi.issuer"].search([])
    issuers.filtered(lambda i: not i.pac_requires_registration)._compute_registered()
