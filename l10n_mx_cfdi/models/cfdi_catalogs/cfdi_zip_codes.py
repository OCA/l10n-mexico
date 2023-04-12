import pytz

from odoo import api, fields, models


class CFDIZipCodes(models.Model):
    _name = "l10n_mx_cfdi.cfdi_zip_codes"
    _description = "CFDI Zip Codes (c_CodigoPostal)"
    _inherit = "l10n_mx_cfdi.catalog_mixin"

    state_id = fields.Many2one("res.country.state", "State", required=False)
    municipality_id = fields.Many2one(
        "l10n_mx_cfdi.cfdi_municipality_code", "Municipality"
    )
    locality_id = fields.Many2one("l10n_mx_cfdi.cfdi_locality_code", "Locality")

    tz_offset = fields.Char("Timezone Offset", required=False)
    tz_offset_dst = fields.Char("Timezone Offset DST", required=False)

    def timezone(self) -> pytz.timezone:
        """
        Resolves the timezone for this zip code based on the
        tz_offset and tz_offset_dst fields and the DST start and end
        times.

        :return: the timezone for this zip code.
        """
        self.ensure_one()

        # TODO: resolve the timezone for this zip code based on the
        # tz_offset and tz_offset_dst fields and the DST start and end
        # times.

        # resolve timezone based on tz_offset
        tz = pytz.FixedOffset(int(self.tz_offset) * 60)
        return tz
