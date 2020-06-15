# Copyright (C) 2019 Wissen MX
# Copyright (C) 2020 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import re

from odoo import _, api, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.constrains("vat", "company_type")
    def check_vat(self):
        if self.vat:
            if self.company_type == "person":
                patron = re.compile(
                    r"^([A-ZÑ\x26]{4}([0-9]{2})(0[1-9]|1[0-2])"
                    r"(0[1-9]|1[0-9]|2[0-9]|3[0-1]))([A-Z\d]{3})?$",
                    re.I,
                )
                if patron.match(self.vat) is None:
                    raise ValidationError(
                        _("The VAT is not valid for a natural person.")
                    )
            elif self.company_type == "company":
                patron = re.compile(
                    r"^([A-ZÑ\x26]{3}([0-9]{2})(0[1-9]|1[0-2])"
                    r"(0[1-9]|1[0-9]|2[0-9]|3[0-1]))([A-Z\d]{3})?$",
                    re.I,
                )
                if patron.match(self.vat) is None:
                    raise ValidationError(_("The VAT is not valid for a moral person."))
