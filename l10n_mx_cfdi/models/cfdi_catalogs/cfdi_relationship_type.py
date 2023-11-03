from odoo import api, fields, models


class CFDIRelationshipType(models.Model):
    _name = "l10n_mx_cfdi.cfdi_relationship_type"
    _description = "CFDI Relationship Type"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
    _l10n_mx_catalog_name = "c_TipoRelacion"
