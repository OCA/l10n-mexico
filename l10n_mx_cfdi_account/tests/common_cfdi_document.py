from odoo.tests.common import TransactionCase


class CFDIDocumentTestCommon(TransactionCase):
    """Provides a registered CFDI issuer, a receiver and published CFDI documents."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "CFDI Customer"})
        cls.issuer = cls.env["l10n_mx_cfdi.issuer"].create(
            {
                "name": "CFDI Issuer",
                "vat": "EKU9003173C9",
                "company_id": cls.company.id,
                "registered": True,
            }
        )

    def _publish_cfdi(self, invoice, **vals):
        """Create a CFDI document for ``invoice`` (published by default)."""
        document = self.env["l10n_mx_cfdi.document"].create(
            {
                "issuer_id": self.issuer.id,
                "receiver_id": self.partner.id,
                "type": "I",
                "serie": "A",
                "folio": "1",
                "state": "published",
                "related_invoice_id": invoice.id,
                **vals,
            }
        )
        invoice.related_cert_ids = [(4, document.id)]
        return document
