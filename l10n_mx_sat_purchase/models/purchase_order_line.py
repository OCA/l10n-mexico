# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import re
import unicodedata

from odoo import models


def normalize_text(value):
    """Lower-case ASCII version of ``value`` without accents nor extra spaces."""
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", value).strip().lower()


def strip_code_prefix(description):
    """Remove the ``[CODE] `` prefix Odoo puts on the names it generates."""
    return re.sub(r"^\[[^\]]*\]\s*", "", description or "")


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _l10n_mx_sat_get_vendor_infos(self, vendor):
        """Vendor pricelist entries of the product for ``vendor``."""
        self.ensure_one()
        return self.product_id.seller_ids.filtered(
            lambda s: s.partner_id.commercial_partner_id == vendor
            and (not s.product_id or s.product_id == self.product_id)
        )

    def _l10n_mx_sat_get_vendor_codes(self, vendor):
        """Upper-case vendor codes of the product for ``vendor``."""
        return {
            code.strip().upper()
            for code in self._l10n_mx_sat_get_vendor_infos(vendor).mapped(
                "product_code"
            )
            if code
        }

    def _l10n_mx_sat_get_descriptions(self, vendor):
        """Normalized descriptions a CFDI concept of this line may carry."""
        self.ensure_one()
        product = self.product_id
        names = [self.name, product.name, product.display_name]
        names += self._l10n_mx_sat_get_vendor_infos(vendor).mapped("product_name")
        if self.name:
            # The line name may be "[CODE] Product\nDescription": match each part
            names += self.name.splitlines()
        names += [strip_code_prefix(name) for name in names]
        return {normalize_text(name) for name in names if name} - {""}
