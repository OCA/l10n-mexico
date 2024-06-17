from base64 import b64encode

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestCFDIDocument(TransactionCase):
    def setUp(self):
        super(TestCFDIDocument, self).setUp()

        self.service = self.env["l10n_mx_cfdi.cfdi_service"].create(
            {
                "name": "Test service",
                "user": "Test user",
                "password": "12345",
            }
        )

        self.issuer = self.env["l10n_mx_cfdi.issuer"].create(
            {
                "name": "Test Issuer",
                "vat": "RFC123456",
                "certificate_file": b64encode(b"certificate"),
                "key_file": b64encode(b"key"),
                "key_password": "password",
                "service_id": self.service.id,
            }
        )

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "vat": "TESTVAT",
                "zip": "12345",
            }
        )

    def test_create_document(self):
        vals = {
            "issuer_id": self.issuer.id,
            "receiver_id": self.partner.id,
            "type": "I",  # Example type, adjust as needed
            # Add other required fields here
        }
        document = self.env["l10n_mx_cfdi.document"].create(vals)
        self.assertEqual(document.state, "draft")

    def test_cancel_document(self):
        document = self.env["l10n_mx_cfdi.document"].create(
            {
                "issuer_id": self.issuer.id,
                "receiver_id": self.partner.id,
                "type": "I",  # Example type, adjust as needed
                # Add other required fields here
            }
        )
        document.publish(cfdi_data={})  # Publish document
        document.cancel(reason="Test Reason")
        self.assertEqual(document.state, "canceled")
        self.assertFalse(document.pdf_file)
        self.assertFalse(document.xml_file)

    def test_publish_document(self):
        document = self.env["l10n_mx_cfdi.document"].create(
            {
                "issuer_id": self.issuer.id,
                "receiver_id": self.partner.id,
                "type": "I",  # Example type, adjust as needed
                # Add other required fields here
            }
        )
        document.publish(cfdi_data={})
        self.assertEqual(document.state, "published")
        self.assertTrue(document.tracking_id)

    def test_action_cancel(self):
        document = self.env["l10n_mx_cfdi.document"].create(
            {
                "issuer_id": self.issuer.id,
                "receiver_id": self.partner.id,
                "type": "I",  # Example type, adjust as needed
                # Add other required fields here
            }
        )
        action = document.action_cancel()
        self.assertEqual(action["res_model"], "l10n_mx_cfdi.document_cancel")

    def test_action_check_status(self):
        document = self.env["l10n_mx_cfdi.document"].create(
            {
                "issuer_id": self.issuer.id,
                "receiver_id": self.partner.id,
                "type": "I",  # Example type, adjust as needed
                # Add other required fields here
            }
        )
        document.publish(cfdi_data={})
        document.action_check_status()
        self.assertNotEqual(document.state, "draft")

    def test_action_get_cancellation_request_proof(self):
        document = self.env["l10n_mx_cfdi.document"].create(
            {
                "issuer_id": self.issuer.id,
                "receiver_id": self.partner.id,
                "type": "I",  # Example type, adjust as needed
                # Add other required fields here
            }
        )
        document.publish(cfdi_data={})
        document.cancel(reason="Test Reason")
        document.action_get_cancellation_request_proof()
        self.assertTrue(document.cancellation_request_proof_file)


# class TestCFDIDocumentRelation(TransactionCase):
#
#     def test_document_relation_creation(self):
#         relation_type = self.env['l10n_mx_catalogs.c_tipo_relacion'].create({
#             'name': 'Test Relation Type',
#             # Add other required fields here
#         })
#         document_1 = self.env['l10n_mx_cfdi.document'].create({
#             # Create document 1 fields
#         })
#         document_2 = self.env['l10n_mx_cfdi.document'].create({
#             # Create document 2 fields
#         })
#         relation = self.env['l10n_mx_cfdi.document_relation'].create({
#             'relation_type_id': relation_type.id,
#             'source_id': document_1.id,
#             'target_id': document_2.id,
#         })
#         self.assertTrue(relation)
#
