# Copyright (C) 2019 Brian McMaster <brian@mcmpest.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestAccountMoveCFDIRelations(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.relation_type = cls.env.ref("l10n_mx_catalogs.c_tipo_relacion_4")
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "vat": "TESTVAT123",
                "zip": "12345",
            }
        )
        cls.issuer = cls.env["l10n_mx_cfdi.issuer"].create(
            {
                "name": "Test Issuer",
                "vat": "RFC123456",
            }
        )
        cls.related_cfdi = cls.env["l10n_mx_cfdi.document"].create(
            {
                "issuer_id": cls.issuer.id,
                "receiver_id": cls.partner.id,
                "type": "I",
                "uuid": "11111111-1111-1111-1111-111111111111",
                "state": "published",
            }
        )

    def test_add_related_cfdis_data_if_needed(self):
        move = self.env["account.move"].new({})
        move.cfdi_document_relation_type = self.relation_type
        move.cfdi_document_relations = self.related_cfdi
        cfdi_data = {}
        move._add_related_cfdis_data_if_needed(cfdi_data)
        self.assertEqual(cfdi_data["Relations"]["Type"], self.relation_type.code)
        self.assertEqual(
            cfdi_data["Relations"]["Cfdis"],
            [{"Uuid": self.related_cfdi.uuid}],
        )

    def test_add_related_cfdis_data_if_needed_without_relations(self):
        move = self.env["account.move"].new({})
        move.cfdi_document_relation_type = self.relation_type
        with self.assertRaises(ValidationError):
            move._add_related_cfdis_data_if_needed({})

    def test_add_related_cfdis_data_if_needed_without_relation_type(self):
        move = self.env["account.move"].new({})
        move.cfdi_document_relations = self.related_cfdi
        cfdi_data = {}
        move._add_related_cfdis_data_if_needed(cfdi_data)
        self.assertNotIn("Relations", cfdi_data)
