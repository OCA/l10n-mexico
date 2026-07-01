# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from datetime import datetime as dt

from odoo import Command, fields, models

_logger = logging.getLogger(__name__)

CFDI_CODE_TO_TAX_TYPE = {"001": "isr", "002": "iva", "003": "ieps"}
CFDI_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_mx_cfdi_uuid = fields.Char(
        string="Fiscal Folio",
        copy=False,
        store=True,
        index="btree_not_null",
        help="CFDI UUID (Folio Fiscal) from SAT.",
    )
    l10n_mx_sat_download_request_id = fields.Many2one(
        comodel_name="l10n_mx_sat.download.request",
        string="SAT Download Request",
        copy=False,
        readonly=True,
    )

    _l10n_mx_cfdi_uuid_company_uniq = models.Constraint(
        "UNIQUE(l10n_mx_cfdi_uuid, company_id)",
        "A CFDI with this UUID already exists for this company.",
    )

    # ------------------------------------------------------------------
    # CFDI XML Parsing helpers
    # ------------------------------------------------------------------

    def _l10n_mx_sat_get_tax_from_cfdi_node(self, tax_node, line, is_withholding=False):
        """Match a CFDI tax node to an Odoo account.tax."""
        tax_code = tax_node.get("Impuesto")
        tax_type = CFDI_CODE_TO_TAX_TYPE.get(tax_code)
        tasa_o_cuota = tax_node.get("TasaOCuota")
        tipo_factor = tax_node.get("TipoFactor")

        if not tasa_o_cuota and tipo_factor != "Exento":
            self.message_post(
                body=self.env._("Tax %s cannot be imported (no rate).", tax_code)
            )
            return self.env["account.tax"]

        if tipo_factor == "Exento":
            amount = 0
        else:
            try:
                amount = float(tasa_o_cuota) * (-100 if is_withholding else 100)
            except (ValueError, TypeError):
                _logger.warning(
                    "Tax %s has invalid rate '%s', skipping",
                    tax_code,
                    tasa_o_cuota,
                )
                return self.env["account.tax"]

        domain = [
            *self.env["account.tax"]._check_company_domain(line.company_id),
            ("amount", "=", amount),
            ("type_tax_use", "=", "purchase"),
            ("amount_type", "=", "percent"),
        ]

        tax_group = self.env.ref(
            f"account.{line.company_id.id}_tax_group_exe_0",
            raise_if_not_found=False,
        )
        if tax_group and tipo_factor == "Exento":
            domain.append(("tax_group_id", "=", tax_group.id))

        if tax_type:
            domain.append(("l10n_mx_tax_type", "=", tax_type))

        taxes = self.env["account.tax"].search(domain, limit=2)
        if not taxes:
            if is_withholding:
                msg = self.env._(
                    "Could not find %(tax_type)s withholding tax at rate %(rate)s%%.",
                    tax_type=tax_type or tax_code,
                    rate=amount,
                )
            else:
                msg = self.env._(
                    "Could not find %(tax_type)s tax at rate %(rate)s%%.",
                    tax_type=tax_type or tax_code,
                    rate=amount,
                )
            self.message_post(body=msg)
        return taxes[:1]

    def _l10n_mx_sat_fill_invoice_line(self, concepto, line):
        """Fill an invoice line from a CFDI Concepto node."""
        clave = concepto.get("ClaveProdServ", "")
        descripcion = concepto.get("Descripcion", "")
        line_name = f"[{clave}] {descripcion}" if clave else descripcion

        tax_ids = []
        for traslado in concepto.findall("{*}Impuestos/{*}Traslados/{*}Traslado"):
            tax = self._l10n_mx_sat_get_tax_from_cfdi_node(traslado, line)
            if tax:
                tax_ids.append(tax.id)
        for retencion in concepto.findall("{*}Impuestos/{*}Retenciones/{*}Retencion"):
            tax = self._l10n_mx_sat_get_tax_from_cfdi_node(
                retencion, line, is_withholding=True
            )
            if tax:
                tax_ids.append(tax.id)

        try:
            discount_amount = float(concepto.get("Descuento") or 0)
            importe = float(concepto.get("Importe") or 0)
            quantity = float(concepto.get("Cantidad", 1))
            price_unit = float(concepto.get("ValorUnitario", 0))
        except (ValueError, TypeError):
            _logger.warning(
                "Concepto with invalid numeric attributes, skipping: %s",
                concepto.get("ClaveProdServ", "?"),
            )
            return
        discount_percent = 0
        if importe and not self.currency_id.is_zero(discount_amount):
            discount_percent = (discount_amount / importe) * 100

        line.write(
            {
                "name": line_name,
                "quantity": quantity,
                "price_unit": price_unit,
                "discount": discount_percent,
                "tax_ids": [Command.set(tax_ids)],
            }
        )

    def _l10n_mx_sat_create_bill_from_cfdi(self, tree, xml_bytes, request):
        """Create a draft vendor bill from a parsed CFDI XML tree.

        :param tree: lxml Element of the CFDI Comprobante
        :param xml_bytes: raw XML bytes for attachment
        :param request: l10n_mx_sat.download.request record
        :return: created account.move or False
        """
        company = request.company_id

        # 1. Extract UUID
        tfd_nodes = tree.xpath("//*[local-name()='TimbreFiscalDigital']")
        if not tfd_nodes:
            _logger.warning("CFDI without TimbreFiscalDigital, skipping")
            return False
        uuid = tfd_nodes[0].get("UUID")
        if not uuid:
            _logger.warning("CFDI without UUID, skipping")
            return False

        # 2. Check duplicate
        existing = self.search(
            [
                ("l10n_mx_cfdi_uuid", "=", uuid),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        if existing:
            _logger.info(
                "CFDI UUID %s already imported (account.move id=%s), skipping",
                uuid,
                existing.id,
            )
            return False

        # 3. Determine move type
        tipo = tree.get("TipoDeComprobante")
        if tipo not in ("I", "E"):
            _logger.info(
                "CFDI TipoDeComprobante=%s not imported as vendor bill "
                "(only I and E are supported), skipping",
                tipo,
            )
            return False
        move_type = "in_refund" if tipo == "E" else "in_invoice"

        # 4. Resolve partner (Emisor for purchase bills)
        emisor = tree.find("{*}Emisor")
        if emisor is None:
            _logger.warning("CFDI UUID %s has no Emisor element, skipping", uuid)
            return False
        rfc = emisor.get("Rfc")
        nombre = emisor.get("Nombre")

        # Generic RFC for foreign (XEXX) and general public (XAXX) partners
        # should not carry VAT; foreign partners skip country_id = MX.
        rfc_foreign = "XEXX010101000"
        rfc_public = "XAXX010101000"

        partner = self.env["res.partner"]._retrieve_partner(
            name=nombre, vat=rfc, company=company
        )
        if not partner and nombre:
            partner_vals = {"name": nombre}
            if rfc != rfc_foreign:
                partner_vals["country_id"] = self.env.ref("base.mx").id
            if rfc not in (rfc_foreign, rfc_public):
                partner_vals["vat"] = rfc
            partner = self.env["res.partner"].create(partner_vals)

        # 5. Resolve currency
        currency_name = tree.get("Moneda", "MXN")
        currency = (
            self.env["res.currency"].search([("name", "=", currency_name)], limit=1)
            or company.currency_id
        )

        # 6. Extract invoice_date
        fecha_timbrado = tfd_nodes[0].get("FechaTimbrado")
        fecha_emision = tree.get("Fecha")
        date_str = fecha_timbrado or fecha_emision
        invoice_date = False
        if date_str:
            invoice_date = dt.strptime(date_str[:19], CFDI_DATE_FORMAT).date()

        # 7. Build ref from Serie + Folio
        serie = tree.get("Serie", "")
        folio = tree.get("Folio", "")
        ref = f"{serie}-{folio}" if serie and folio else folio or uuid[:8]

        # 8. Find purchase journal
        journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", company.id)],
            limit=1,
        )
        if not journal:
            _logger.warning("No purchase journal found for company %s", company.name)
            return False

        # 9. Create the move
        move = self.with_company(company).create(
            {
                "move_type": move_type,
                "journal_id": journal.id,
            }
        )

        with move._get_edi_creation() as move:
            move.partner_id = partner
            move.currency_id = currency
            move.invoice_date = invoice_date
            move.ref = ref
            move.l10n_mx_sat_download_request_id = request.id

            for concepto in tree.findall("{*}Conceptos/{*}Concepto"):
                line = self.env["account.move.line"].create(
                    {"move_id": move.id, "company_id": company.id}
                )
                move._l10n_mx_sat_fill_invoice_line(concepto, line)

        # 10. Store CFDI XML as attachment
        self.env["ir.attachment"].create(
            {
                "name": f"{uuid}.xml",
                "raw": xml_bytes,
                "res_model": "account.move",
                "res_id": move.id,
                "mimetype": "application/xml",
            }
        )

        # 11. Write UUID directly
        move.l10n_mx_cfdi_uuid = uuid

        # 12. Chatter message
        move.message_post(
            body=self.env._(
                "Vendor bill imported from SAT Descarga Masiva. UUID: %s", uuid
            ),
        )

        return move
