from . import models
from . import wizards


def post_init_hook(env):
    """Recompute the display name of the documents downloaded before install."""
    documents = env["l10n_mx_sat.document"].search([])
    env.add_to_compute(documents._fields["display_name"], documents)
    documents.mapped("display_name")
