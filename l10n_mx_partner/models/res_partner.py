# Copyright 2022 Jarsa
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re

from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_mx_edi_fiscal_regime = fields.Selection(
        selection=[
            ("601", "General de Ley Personas Morales"),
            ("603", "Personas Morales con Fines no Lucrativos"),
            ("605", "Sueldos y Salarios e Ingresos Asimilados a Salarios"),
            ("606", "Arrendamiento"),
            ("607", "Régimen de Enajenación o Adquisición de Bienes"),
            ("608", "Demás ingresos"),
            ("609", "Consolidación"),
            (
                "610",
                "Residentes en el Extranjero sin Establecimiento Permanente en México",
            ),
            ("611", "Ingresos por Dividendos (socios y accionistas)"),
            ("612", "Personas Físicas con Actividades Empresariales y Profesionales"),
            ("614", "Ingresos por intereses"),
            ("615", "Régimen de los ingresos por obtención de premios"),
            ("616", "Sin obligaciones fiscales"),
            (
                "620",
                "Sociedades Cooperativas de Producción que optan por diferir sus ingresos",
            ),
            ("621", "Incorporación Fiscal"),
            ("622", "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras"),
            ("623", "Opcional para Grupos de Sociedades"),
            ("624", "Coordinados"),
            (
                "625",
                "Régimen de las Actividades Empresariales con ingresos a través de "
                "Plataformas Tecnológicas",
            ),
            ("626", "Régimen Simplificado de Confianza - RESICO"),
        ],
        string="Fiscal Regime",
        help="It is used to fill Mexican XML CFDI required field "
        "Comprobante.Receptor.RegimenFiscalReceptor.",
    )

    @api.model
    def _l10n_mx_format_vat(self, vat):
        special_chars = "!\"#$%/()=?¡¨*[];:_'¿´+{},.-><°|@¬\\~`^ "
        for char in special_chars:
            vat = vat.replace(char, "")
        return vat.upper()

    @api.onchange("vat")
    def _onchange_l10n_mx_vat(self):
        if not self.vat or self.country_id and self.country_id.code != "MX":
            return False
        self.vat = self._l10n_mx_format_vat(self.vat)
        person_pattern = "^[A-ZÑ\x26]{4}([0-9]{2})(0[1-9]|1[0-2])(0[1-9]|1[0-9]|2[0-9]|3[0-1])([A-Z]|[0-9]){2}([A]|[0-9]){1}?$"  # noqa: B950
        company_pattern = "^[A-ZÑ\x26]{3}([0-9]{2})(0[1-9]|1[0-2])(0[1-9]|1[0-9]|2[0-9]|3[0-1])([A-Z]|[0-9]){2}([A]|[0-9]){1}?$"  # noqa: B950
        if re.match(person_pattern, self.vat):
            self.company_type = "person"
        elif re.match(company_pattern, self.vat):
            self.company_type = "company"
        else:
            return {
                "warning": {
                    "title": _("Warning"),
                    "message": _("VAT is not valid"),
                }
            }
