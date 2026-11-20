from odoo import models


class Document(models.Model):
    _inherit = "l10n_mx_cfdi.document"

    def _resolve_report(self):
        self.ensure_one()
        if self.type == "T":
            waybills = self.env["l10n_mx_cfdi_waybill.waybill"].search(
                [("cfdi_id", "=", self.id)]
            )
            return "l10n_mx_cfdi_waybill.action_waybill_report", waybills.ids
        return super()._resolve_report()

    def _set_serie_and_folio_from_document_sequence(self, vals):
        if vals["type"] != "T":
            return super()._set_serie_and_folio_from_document_sequence(vals)

        vals["serie"] = "CP"
        vals["folio"] = "(Borrador)"
