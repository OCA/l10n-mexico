# Copyright (C) 2019 Wissen MX
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import re
from odoo import api, fields, models, fields, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    @api.constrains('vat', 'company_type')
    def check_vat(self):
        if self.vat:
            if self.company_type == 'person':
                patron = re.compile(
                    '^([A-ZÑ\x26]{4}([0-9]{2})(0[1-9]|1[0-2])(0[1-9]|1[0-9]|2[0-9]|3[0-1]))([A-Z\d]{3})?$', re.I)
                if patron.match(self.vat) == None:
                    raise ValidationError(_('The VAT is not valid for a natural person.'))
            elif self.company_type == 'company':
                patron = re.compile(
                    '^([A-ZÑ\x26]{3}([0-9]{2})(0[1-9]|1[0-2])(0[1-9]|1[0-9]|2[0-9]|3[0-1]))([A-Z\d]{3})?$', re.I)
                if patron.match(self.vat) == None:
                    raise ValidationError(_('The VAT is not valid for a moral person.'))
