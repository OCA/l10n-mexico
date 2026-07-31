from odoo import api, fields, models


class CertificateCancel(models.TransientModel):
    _name = "l10n_mx_cfdi_account.document_cancel"
    _description = "Certificate Cancel"

    certificate_ids = fields.Many2many(
        "l10n_mx_cfdi.document", string="Certificados", required=True
    )
    cancel_reason_id = fields.Many2one(
        "l10n_mx_catalogs.c_motivo_cancelacion", string="Razón", required=True
    )
    replacement_certificate_id = fields.Many2one(
        "l10n_mx_cfdi.document", string="Reemplazo"
    )
    single_cancel = fields.Boolean(default=True)

    related_invoices = fields.Many2many("account.move", string="Facturas Relacionadas")

    requires_replacement = fields.Boolean(
        compute="_compute_requires_replacement", store=False
    )
    simulate_operation = fields.Boolean(
        default=False,
        help="Simulate the cancel operation without sending the request to the SAT",
        groups="base.group_system",
    )

    @api.depends("cancel_reason_id")
    def _compute_requires_replacement(self):
        for record in self:
            record.requires_replacement = record.cancel_reason_id.code == "01"

    @api.model
    def default_get(self, field_names):
        defaults_dict = super().default_get(field_names)
        context = self.env.context

        if context.get("active_model") == "account.move":
            related_invoice_objs = self.env["account.move"].browse(
                context["active_ids"]
            )
            defaults_dict.update(
                {
                    "certificate_ids": (
                        related_invoice_objs.related_cert_ids.filtered_domain(
                            [("state", "=", "published")]
                        )
                    ),
                    "related_invoices": related_invoice_objs,
                    "cancel_reason_id": self.env.ref(
                        "l10n_mx_catalogs.c_motivo_cancelacion_02"
                    ).id,
                }
            )

        return defaults_dict

    def cancel_certificate(self):
        feedback_lines = []
        for record in self:
            for certificate in record.certificate_ids:
                if certificate.state == "published":
                    feedback = certificate.cancel(
                        record.cancel_reason_id.code,
                        record.replacement_certificate_id,
                        record.simulate_operation,
                    )
                    feedback_lines.append(certificate._format_cancel_feedback(feedback))

            for invoice in record.certificate_ids.related_invoice_id:
                invoice._compute_cfdi_document_id()

                if self.env.company.l10n_mx_cfdi_auto:
                    invoice.button_draft()

            for payment in record.certificate_ids.related_payment_id:
                payment.move_id._compute_cfdi_document_id()

        if feedback_lines:
            body = "\n".join(feedback_lines)
        else:
            body = self.env._("No published CFDI was cancelled.")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("CFDI cancellation"),
                "message": body,
                "type": "success" if feedback_lines else "warning",
                "sticky": True,
            },
        }
