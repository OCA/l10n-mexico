from odoo import api, fields, models


class CFDIRelationshipType(models.Model):
    _name = "l10n_mx_cfdi.cfdi_relationship_type"
    _description = "CFDI Relationship Type (c_TipoRelacion)"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
