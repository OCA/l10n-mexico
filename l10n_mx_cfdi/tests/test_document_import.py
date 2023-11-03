import base64
import csv
import os

from .utils import load_csv_fixtures
from odoo.tests import tagged, TransactionCase


@tagged("-standard", "l10n_mx_cfdi")
class TestCFDIDocument_4_0Model(TransactionCase):
    """
    Test importing and exporting CFDI XML files into Comprobante Model
    """

    def setUp(self):
        # get Comprobante class file path

        l10n_mx_cfdi_spec_path = os.path.dirname(__file__)
        test_data_dir_path = os.path.join(
            l10n_mx_cfdi_spec_path,
            "..",
            "data",
            "tests",
        )

        self.cfdi_invoice_4_0_xml_path = os.path.join(
            test_data_dir_path, "cfdi_4_0_invoice.xml"
        )

        self.assertTrue(os.path.exists(self.cfdi_invoice_4_0_xml_path))
        with open(self.cfdi_invoice_4_0_xml_path, "rb") as xml_file:
            self.cfdi_invoice_4_0_data = xml_file.read()

        fixtures_dir_path = os.path.join(
            test_data_dir_path,
            "fixtures",
        )

        load_csv_fixtures(self.env, fixtures_dir_path)

    def _load_csv_fixtures(self, fixtures_dir_path):
        # load fixtures from data/tests/l10n_mx_cfdi.cfdi_type.csv
        cfdi_type_data_path = os.path.join(
            fixtures_dir_path, "l10n_mx_cfdi.cfdi_type.csv"
        )
        with open(cfdi_type_data_path, "rb") as csv_file:
            # open using csv.DictReader
            csv_reader = csv.DictReader(csv_file)
            # create a list of dictionaries
            for entry in csv_reader:
                self.env["l10n_mx_cfdi.cfdi_type"].create(entry)

    def test_import(self):
        """
        Test importing cfdi_4_0_invoice.xml into Comprobante class
        """

        import_wizard = self.env["l10n_mx_cfdi.cfdi_document_import_wizard"].create(
            {
                "xml_file": self.cfdi_invoice_4_0_data,
            }
        )

        res = import_wizard._import_xml(self.cfdi_invoice_4_0_data)
        self.assertTrue(res)

        # assert Comprobante data
        self._assert_comprobante_data_parsed_properly(res)

        # assert Attachment data
        cfdi_attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "l10n_mx_cfdi.document_4_0"),
                ("res_id", "=", res.id),
            ],
            limit=1,
        )

        cfdi_attachment_data = base64.b64decode(cfdi_attachment.datas)
        self.assertEqual(cfdi_attachment_data, self.cfdi_invoice_4_0_data)

    def _assert_comprobante_data_parsed_properly(self, res):
        self.assertEqual(res.cfdi_type.code, "I")
        self.assertEqual(res.series, "INV2023")
        self.assertEqual(res.folio, "00008")
        self.assertEqual(str(res.date), "2023-05-02 00:43:27")
        self.assertEqual(res.expedition_zip_code.code, "26015")
        # assert issuer data
        self.assertEqual(res.issuer_id.name, "ESCUELA KEMPER URGATE")
        self.assertEqual(res.issuer_id.vat, "EKU9003173C9")
        # assert receiver data
        self.assertEqual(res.receiver_id.name, "XOCHILT CASAS CHAVEZ")
        self.assertEqual(res.receiver_id.vat, "CACX7605101P8")

        self.assertEqual(res.uuid, "ca964608-b68c-489e-b41f-ba0c2129e578")
