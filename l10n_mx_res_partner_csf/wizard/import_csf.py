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
        partner_obj = self.env["res.partner"]
        temp_path = tempfile.gettempdir()
        file_data = base64.decodebytes(self.file)
        fp = open(temp_path + "/csf.pdf", "wb+")
        fp.write(file_data)
        fp.close()
        try:
            text = extract_text(temp_path + "/csf.pdf")
        except Exception as e:
            raise UserError(_("Uploaded file is not in PDF format (%s).") % e) from e
        vals = self.prepare_res_partner_values(text)
        partner_obj.browse(self._context.get("active_id")).write(vals)
        self.attach_csf()

    def prepare_res_partner_values(self, text):
        state_obj = self.env["res.country.state"]
        split_data = text.split("\n")
        vat = name = zip = city = street = street2 = state = ""
        for index, line in enumerate(split_data):
            if "CÉDULA DE IDENTIFICACIÓN FISCAL" in line:
                vat += split_data[index + 2].strip()
            elif "Registro Federal de Contribuyentes" in line:
                name += split_data[index + 2].strip()
                if split_data[index + 3] == "":
                    name += " " + split_data[index + 4].strip()
                elif split_data[index + 3].isupper():
                    name += " " + split_data[index + 3].strip()
            elif "Código Postal" in line:
                zip += line.split(":")[-1].strip()
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
                city += line.split(":")[-1].strip()
            elif "Nombre de la Entidad Federativa" in line:
                state = line.split("Nombre de la Entidad Federativa:")[-1].strip()

        country_id = self.env.ref("base.mx")
        state_id = state_obj.search(
            [("country_id", "=", country_id.id), ("name", "ilike", state)], limit=1
        )

        return {
            "vat": vat,
            "name": name,
            "zip": zip,
            "city": city,
            "street": street,
            "street2": street2,
            "state_id": state_id.id or False,
            "country_id": country_id.id,
        }
