# Copyright 2026 Gray Matter Logic
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from lxml import etree

from odoo.tests import TransactionCase
from odoo.tools.template_inheritance import apply_inheritance_specs

# Anchors used by account_edi_ubl_cii.layout_invoices_generated_by_odoo.
# That view is primary, so Odoo checks it when this layout is updated.
UBL_HEADER_XPATH = (
    "//div[contains(@t-attf-class, 'header')]"
    "//div[hasclass('d-flex', 'justify-content-between')]"
)
UBL_LAYOUT_SPECS = f"""
<data>
    <xpath expr="{UBL_HEADER_XPATH}" position="replace">
        <div class="mb-2" style="height: 50px"/>
    </xpath>
    <xpath expr="//div[@name='company_address']" position="replace">
        <div class="col-6" name="company_address"/>
    </xpath>
</data>
"""


class TestExternalLayoutStandard(TransactionCase):
    def test_standard_layout_keeps_ubl_cii_header_anchor(self):
        source = self.env.ref("web.external_layout_standard")._get_combined_arch()
        apply_inheritance_specs(source, etree.fromstring(UBL_LAYOUT_SPECS))
