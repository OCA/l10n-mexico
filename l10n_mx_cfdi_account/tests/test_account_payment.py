# from odoo.exceptions import ValidationError
# from odoo.tests import TransactionCase
#
#
# class TestAccountPayment(TransactionCase):
#
#     def setUp(self):
#         super().setUp()
#
#         # Create test data
#         self.partner = self.env["res.partner"].create(
#             {
#                 "name": "Test Partner",
#                 "vat": "TESTVAT",
#                 "zip": "12345",  # Add other required fields
#             }
#         )
#
#         self.payment_journal = self.env["account.journal"].create(
#             {
#                 "name": "Test Journal",
#                 "code": "TEST",
#                 "type": "sale",
#             }
#         )
#
#         self.payment_method = self.env["account.payment.method"].create(
#             {
#                 "name": "Test Payment Method",
#                 "code": "TEST_PM",
#                 "payment_type": "inbound",  # Adjust payment type as needed
#             }
#         )
#
#         self.payment_method_line = self.env["account.payment.method.line"].create(
#             {
#                 "payment_method_id": self.payment_method.id,
#                 "payment_type": "inbound",  # Adjust payment type as needed
#                 "journal_id": self.payment_journal.id,
#                 "sequence": 1,
#                 # Add other required fields
#             }
#         )
#
#         self.payment = self.env["account.payment"].create(
#             {
#                 "partner_id": self.partner.id,
#                 "journal_id": self.payment_journal.id,
#                 "amount": 100.0,
#                 "payment_type": "inbound",
#                 "payment_method_line_id": self.payment_method_line.id,
#             }
#         )
#
#         self.issuer = self.env["res.partner"].create(
#             {
#                 "name": "Issuer",
#                 "vat": "ISSUERVAT",
#                 "zip": "54321",  # Add other required fields
#             }
#         )
#
#         self.invoice = self.env["account.move"].create(
#             {
#                 "partner_id": self.partner.id,
#                 "type": "out_invoice",  # Example type, adjust as needed
#                 "issuer_id": self.issuer.id,
#                 "amount_total": 50.0,  # Example amount, adjust as needed
#                 # Add other required fields
#             }
#         )
#
#         self.payment.reconciled_invoice_ids = [(4, self.invoice.id)]
#
#     def test_action_generate_cfdi_with_existing_cfdi(self):
#         # Add a related CFDI to the payment
#         self.payment.write(
#             {"cfdi_document_id": self.env["l10n_mx_cfdi.document"].create({}).id}
#         )
#
#         # Try to generate CFDI again, it should raise validation error
#         with self.assertRaises(ValidationError):
#             self.payment.action_generate_cfdi()
#
#     def test_action_generate_cfdi_not_fully_reconciled(self):
#         # Try to generate CFDI for a payment that is not fully reconciled
#         with self.assertRaises(ValidationError):
#             self.payment.action_generate_cfdi()
#
#     def test_create_payment_cfdi(self):
#         # Create a fully reconciled payment
#         self.payment.move_type = "entry"
#         self.payment.is_reconciled = True
#         self.payment.create_payment_cfdi()
#
#         # Check if the payment has a related CFDI
#         self.assertTrue(self.payment.cfdi_document_id)
#         self.assertEqual(self.payment.cfdi_document_id.type, "P")
#         self.assertEqual(self.payment.cfdi_document_id.issuer_id.zip, "12345")
#         self.assertEqual(self.payment.cfdi_document_id.receiver_id.vat, "TESTVAT")
#
#     def test_create_payment_cfdi_with_legacy_invoice(self):
#         # Create a fully reconciled payment with a legacy invoice
#         self.payment.move_type = "entry"
#         self.payment.is_reconciled = True
#         self.payment.reconciled_invoice_ids = [
#             (
#                 0,
#                 0,
#                 {
#                     "related_cert_ids": [
#                         (
#                             0,
#                             0,
#                             {
#                                 "type": "I",
#                                 "state": "published",
#                                 "receiver_id": self.partner.id,
#                             },
#                         )
#                     ]
#                 },
#             )
#         ]
#
#         # Now, receiver should be resolved from invoice CFDI
#         self.payment.create_payment_cfdi()
#
#         # Check if the payment has a related CFDI
#         self.assertTrue(self.payment.cfdi_document_id)
#
#     def test_cancel_payment_cfdi(self):
#         # Create a payment with related CFDI
#         self.payment.move_type = "entry"
#         self.payment.is_reconciled = True
#         self.payment.create_payment_cfdi()
#
#         # Cancel the payment CFDI
#         self.payment.cancel_payment_cfdi()
#
#         # Check if the CFDI is canceled
#         self.assertEqual(self.payment.cfdi_document_id.state, "canceled")
