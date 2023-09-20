import base64
import logging
import tempfile

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from pdfminer.high_level import extract_text
except ImportError as err:
    _logger.debug(err)


class ImportCSF(models.TransientModel):
    _name = "import.csf"

    file = fields.Binary(required=True, attachment=True)
    file_name = fields.Char()

    def attach_csf(self):
        self.env["ir.attachment"].create(
            {
                "name": self.file_name,
                "datas": self.file,
                "res_model": "res.partner",
                "res_id": self._context.get("active_id"),
            }
        )

    def upload_csf(self):
        state_obj = self.env["res.country.state"]
        partner_obj = self.env["res.partner"]
        if self.file_name.split(".")[-1] != "pdf":
            raise UserError(_("Upload file is not in PDF format"))
        temp_path = tempfile.gettempdir()
        file_data = base64.decodebytes(self.file)
        fp = open(temp_path + "/csf.pdf", "wb+")
        fp.write(file_data)
        fp.close()

        vals = {}
        text = extract_text(temp_path + "/csf.pdf")
        index = 0
        split_data = text.split("\n")
        street = street2 = state = ""
        for line in split_data:
            temp_index = index + 2
            if "RFC" in line:
                vals.update({"vat": split_data[temp_index].strip()})
            elif "Denominación/Razón Social" in line:
                vals.update({"name": split_data[temp_index].strip()})
            elif "Código Postal" in line:
                vals.update({"zip": line.split(":")[-1].strip()})
            elif "Tipo de Vialidad" in line:
                street += line.split("Tipo de Vialidad:")[-1].strip() + " "
            elif "Nombre de Vialidad" in line:
                street += line.split("Nombre de Vialidad:")[-1].strip() + " "
            elif "Número Exterior" in line:
                street += line.split("Número Exterior:")[-1].strip()
            elif "Número Interior" in line:
                street2 += line.split("Número Interior:")[-1].strip() + " "
            elif "Nombre de la Colonia" in line:
                street2 += line.split("Nombre de la Colonia:")[-1].strip()
            elif "Nombre del Municipio o Demarcación Territorial" in line:
                vals.update({"city": line.split(":")[-1].strip()})
            elif "Nombre de la Entidad Federativa" in line:
                state = line.split("Nombre de la Entidad Federativa:")[-1].strip()

            index += 1

        country_id = self.env.ref("base.mx")
        state_id = state_obj.search(
            [("country_id", "=", country_id.id), ("name", "ilike", state)]
        )

        vals.update(
            {
                "street": street,
                "street2": street2,
                "state_id": state_id.id,
                "country_id": country_id.id,
            }
        )
        if vals:
            partner_obj.browse(self._context.get("active_id")).write(vals)
            self.attach_csf()
