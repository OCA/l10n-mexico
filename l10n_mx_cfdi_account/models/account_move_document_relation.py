from odoo import fields, models


class AccountMoveDocumentRelation(models.Model):
    _name = "account.move.document.relation"
    _description = "Account Move Document Relation"

    move_id = fields.Many2one(
        "account.move",
        required=True,
        ondelete="cascade",
        index=True,
    )
    relation_type_id = fields.Many2one(
        "l10n_mx_catalogs.c_tipo_relacion",
        string="Relation Type",
        required=True,
    )
    relation_type_name = fields.Char(
        string="Relation Type Description",
        related="relation_type_id.name",
    )
    target_uuid = fields.Char(
        string="CFDI UUID",
        required=True,
        size=36,
    )
