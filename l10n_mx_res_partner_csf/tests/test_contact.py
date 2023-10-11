# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import os

from odoo import tools
from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestContact(TransactionCase):
    def setUp(self):
        super().setUp()
        self.country_id = self.env.ref("base.mx")
        self.import_obj = self.env["import.csf"]
        self.partner = self.env["res.partner"].create(
            {
                "name": "Demo",
            }
        )

    def test_import_csf(self):
        action = self.partner.action_upload_csf()
        generated_file = os.path.join("l10n_mx_res_partner_csf", "tests", "demo.pdf")
        generated_file = tools.misc.file_open(generated_file, "rb")
        data = base64.encodebytes(generated_file.read())
        record_csf = (
            self.env[action.get("res_model")]
            .with_context(active_id=self.partner.id)
            .create({"file": data, "file_name": "demo.txt"})
        )
        with self.assertRaises(UserError):
            record_csf.upload_csf()

        record1 = self.import_obj.with_context(active_id=self.partner.id).create(
            {"file": data, "file_name": "demo.pdf"}
        )

        record1.upload_csf()

        self.assertEqual("OSI220401JP1", self.partner.vat)
        self.assertEqual("OPEN SOURCE INTEGRATORS", self.partner.name)
        self.assertEqual("76100", self.partner.zip)
        self.assertEqual("AVENIDA (AV.) ANTEA 1032", self.partner.street)
        self.assertEqual(" JURICA", self.partner.street2)
        self.assertEqual("QUERETARO", self.partner.city)
        self.assertEqual(self.country_id.id, self.partner.country_id.id)
