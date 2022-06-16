# Copyright 2022 Jarsa
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re
from base64 import b64decode

import pytesseract
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFPageCountError

from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    cif_file = fields.Binary(
        string="Attach CIF File",
        copy=False,
    )

    @api.model
    def _get_cif_pattern_dict(self):
        return {
            "vat": "RFC:",
            "name": "Social:",
            "first_name": "Nombre (s):",
            "last_name": "Primer Apellido:",
            "second_last_name": "Segundo Apellido:",
            "zip": "Postal:",
            "street_name": "bre de Vialidad:",
            "street_number": "Numero Exterior:",
            "street_number2": "Interior:",
            "l10n_mx_edi_colony": "Nombre de la Colonia:",
            "phone": "Tel. Fijo Lada:",
            "mobile": "Tel. Movil Lada:",
            "phonenumber": "Numero:",
            "email": "nico:",
        }

    @api.model
    def _get_regex_patterns(self):
        return ["(.*?)\\n", "\\n\\n(.*?)", "\\n\\n(.*?)\\n", "(.*?) ", "(.*?):"]

    @api.model
    def _process_cif_vals(self, vals):
        if (
            vals.get("first_name")
            and vals.get("last_name")
            and vals.get("second_last_name")
        ):
            vals["name"] = "%(first_name)s %(last_name)s %(second_last_name)s" % vals
            vals.pop("first_name")
            vals.pop("last_name")
            vals.pop("second_last_name")
        if vals.get("street_name"):
            vals["street_name"] = (
                vals.get("street_name").split("Numero Exterior")[0].strip()
            )
        if vals.get("email") and vals.get("email").startswith("—"):
            vals["email"] = vals.get("email")[1:].strip()
        if vals.get("email") and vals.get("email").startswith("©"):
            vals["email"] = vals.get("email")[1:].strip()
        if vals.get("email") and vals.get("email").startswith("_"):
            vals["email"] = vals.get("email")[1:].strip()
        if vals.get("street_number2") and "Nombre de la Colonia" in vals.get(
            "street_number2"
        ):
            vals["street_number2"] = (
                vals.get("street_number2").split("Nombre de la Colonia")[0].strip()
                or False
            )
        if vals.get("phonenumber"):
            if vals.get("phone"):
                if "Numero:" in vals.get("phone"):
                    vals["phone"] = vals.get("phone").split("Numero")[0].strip()
                vals["phone"] = vals.get("phone") + vals.get("phonenumber")
            if vals.get("mobile"):
                if "Numero:" in vals.get("mobile"):
                    vals["mobile"] = vals.get("mobile").split("Numero")[0].strip()
                vals["mobile"] = vals.get("mobile") + vals.get("phonenumber")
            vals.pop("phonenumber")
        if vals.get("zip"):
            vals["zip"] = vals.get("zip").split("Tipo de Vialidad")[0].strip()
            zip_code = self.env["res.city.zip"].search(
                [
                    ("name", "=", vals.get("zip")),
                    ("country_id.code", "=", "MX"),
                ]
            )
            if len(zip_code) > 1 and vals.get("l10n_mx_edi_colony"):
                filtered_zip = zip_code.filtered(
                    lambda zip: vals.get("l10n_mx_edi_colony").lower()
                    in zip.l10n_mx_edi_colony.lower()
                )
                if filtered_zip:
                    zip_code = filtered_zip
            if zip_code:
                vals.update(
                    {
                        "zip_id": zip_code[0].id,
                    }
                )
        return vals

    @api.model
    def _get_fiscal_regime(self, text):
        fiscal_regimes = self._fields["l10n_mx_edi_fiscal_regime"].selection
        for key, value in fiscal_regimes:
            if value in text:
                return key
        return False

    @api.onchange("cif_file")
    def _onchange_cif_file(self):
        if not self.cif_file:
            return
        file = b64decode(self.cif_file)
        try:
            pages = convert_from_bytes(file)
        except PDFPageCountError:
            return {
                "warning": {
                    "title": _("Error"),
                    "message": _("The file is not a valid PDF"),
                },
            }
        text = ""
        for page in pages:
            text += pytesseract.image_to_string(page)
        patterns_dict = self._get_cif_pattern_dict()
        vals = {
            "l10n_mx_edi_fiscal_regime": self._get_fiscal_regime(text),
        }
        regex_patterns = self._get_regex_patterns()
        for name, pattern in patterns_dict.items():
            for regex_pattern in regex_patterns:
                match = re.search(re.escape(pattern) + regex_pattern, text)
                if match and match.group(1):
                    vals[name] = match.group(1).strip()
                    break
        vals = self._process_cif_vals(vals)
        self.update(vals)
