from odoo import models


class Document(models.Model):
    _inherit = "l10n_mx_cfdi.document"

    def _resolve_report(self):
        self.ensure_one()
        if self.type == "T":
            report_type = "l10n_mx_cfdi_waybill.action_waybill_report"
            report = self.env.ref(report_type)
            # resolve related waybill
            resource_ids = (
                self.env["l10n_mx_cfdi_waybill.waybill"]
                .search([("cfdi_id", "=", self.id)])
                .ids
            )

            return report_type, report, resource_ids
        else:
            return super()._resolve_report()

    def _set_serie_and_folio_from_document_sequence(self, vals):
        if vals["type"] != "T":
            return super()._set_serie_and_folio_from_document_sequence(vals)

        vals["serie"] = "CP"
        vals["folio"] = "(Borrador)"
