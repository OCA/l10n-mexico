from odoo import api, fields, models


class CFDIProductAndServiceCode(models.Model):
    _name = "l10n_mx_cfdi.cfdi_product_and_service_code"
    _description = "CFDI Product and Service Code"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
    _l10n_mx_catalog_name = "c_ClaveProdServ"

    include_transferred_iva = fields.Selection(
        [
            ("0", "No"),
            ("1", "Yes"),
            ("2", "Optional"),
        ],
        string="Include Transferred IVA",
        required=True,
        default="2",
    )

    include_transferred_ieps = fields.Selection(
        [
            ("0", "No"),
            ("1", "Yes"),
            ("2", "Optional"),
        ],
        string="Include Transferred IEPS",
        required=True,
        default="2",
    )
