# Copyright (C) 2023 Open Source Integrators
# (https://www.opensourceintegrators.com).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    audi_business_unit = fields.Char(string="Business Unit")
    audi_applicant_email = fields.Char(string="Applicant email")
    audi_flag = fields.Boolean(compute="_compute_audi_flag", store=True)
    audi_tax_code = fields.Char(string="Tax Code")
    audi_fiscal_document_type = fields.Char(string="Fiscal Document Type")
    audi_document_type = fields.Char(string="Document Type")

    @api.depends("partner_id.l10n_mx_edi_addenda")
    def _compute_audi_flag(self):
        for record in self:
            record.audi_flag = (
                record.partner_id.l10n_mx_edi_addenda_name == "Addenda Audi"
            )

    def _l10n_mx_edi_addenda_audi_render(self):
        """Render the Audi addenda QWeb template for this invoice."""
        self.ensure_one()
        return self.env["ir.qweb"]._render(
            "l10n_mx_cfdi_account_addenda_audi.l10n_mx_cfdi_account_addenda_audi",
            {"record": self},
        )

    def create_invoice_cfdi(self):
        res = super().create_invoice_cfdi()
        if self.audi_flag:
            self._l10n_mx_edi_addenda_audi_attach()
        return res

    def _l10n_mx_edi_addenda_audi_attach(self):
        """Attach rendered Audi addenda to the published CFDI via Facturama."""
        self.ensure_one()
        document = self.cfdi_document_id
        if not document or not document.tracking_id:
            return False
        addenda_xml = self._l10n_mx_edi_addenda_audi_render()
        if isinstance(addenda_xml, bytes):
            addenda_xml = addenda_xml.decode("utf-8")
        service = document.issuer_id.service_id.sudo()
        return service.attach_addenda(document.tracking_id, addenda_xml)
