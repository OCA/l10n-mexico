# -*- coding: utf-8 -*-
import re
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'
    @api.constrains('vat', 'company_type')
    def _rfc(self):
        if self.vat:
            if self.company_type == 'person':
                patron = re.compile(
                    '^([A-ZÑ\x26]{4}([0-9]{2})(0[1-9]|1[0-2])(0[1-9]|1[0-9]|2[0-9]|3[0-1]))([A-Z\d]{3})?$', re.I)
                if patron.match(self.vat) == None:
                    raise ValidationError('RFC de personas fisicas no valido')
            elif self.company_type == 'company':
                patron = re.compile(
                    '^([A-ZÑ\x26]{3}([0-9]{2})(0[1-9]|1[0-2])(0[1-9]|1[0-9]|2[0-9]|3[0-1]))([A-Z\d]{3})?$', re.I)
                if patron.match(self.vat) == None:
                    raise ValidationError('RFC de personas morales no valido')
