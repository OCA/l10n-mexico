# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.tests.common import TransactionCase

# Fictitious RFCs and data — never use real taxpayer information in tests.
RECEPTOR_RFC = "EKU9003173C9"  # SAT's official test RFC
EMISOR_RFC = "XIA190128J61"  # Fictitious
EMISOR_NAME = "SOLUCIONES DEMO SA DE CV"
RFC_FOREIGN = "XEXX010101000"
RFC_PUBLIC = "XAXX010101000"


class VendorBillTestCommon(TransactionCase):
    """Shared setup and CFDI XML helpers for vendor bill tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.company.write(
            {
                "vat": RECEPTOR_RFC,
                "country_id": cls.env.ref("base.mx").id,
            }
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)],
            limit=1,
        )
        if not cls.journal:
            cls.journal = cls.env["account.journal"].create(
                {
                    "name": "Vendor Bills",
                    "code": "BILL",
                    "type": "purchase",
                    "company_id": cls.company.id,
                }
            )
        cls.request = cls.env["l10n_mx_sat.download.request"].create(
            {
                "company_id": cls.company.id,
                "document_kind": "cfdi",
                "direction": "received",
                "request_type": "xml",
                "date_from": "2026-02-01 00:00:00",
                "date_to": "2026-02-28 23:59:59",
                "state": "downloading",
            }
        )

    def _parse(self, xml_bytes):
        return etree.fromstring(xml_bytes)

    def _create_bill(self, xml_bytes, request=None):
        return self.env["account.move"]._l10n_mx_sat_create_bill_from_cfdi(
            self._parse(xml_bytes),
            xml_bytes,
            request or self.request,
        )

    def _cfdi_xml(
        self,
        *,
        uuid="aabbccdd-1111-2222-3333-444455556666",
        tipo="I",
        folio="1001",
        serie=None,
        moneda="MXN",
        emisor_rfc=EMISOR_RFC,
        emisor_nombre=EMISOR_NAME,
        include_emisor=True,
        include_tfd=True,
        tfd_uuid=None,
        fecha="2026-02-26T16:57:09",
        fecha_timbrado="2026-02-26T16:57:10",
        conceptos=None,
    ):
        """Build a minimal CFDI XML with optional variants for edge cases."""
        serie_attr = f' Serie="{serie}"' if serie else ""
        folio_attr = f' Folio="{folio}"' if folio is not None else ""
        emisor = ""
        if include_emisor:
            emisor = (
                f'<cfdi:Emisor Rfc="{emisor_rfc}" '
                f'Nombre="{emisor_nombre}" RegimenFiscal="601"/>'
            )
        if conceptos is None:
            conceptos = """
        <cfdi:Concepto ClaveProdServ="43232400" Cantidad="1"
            ClaveUnidad="E48" Unidad="Unidad de servicio"
            Descripcion="Servicio de consultoria mensual"
            ValorUnitario="1422.41" Importe="1422.41"
            Descuento="0.00" ObjetoImp="02">
            <cfdi:Impuestos>
                <cfdi:Traslados>
                    <cfdi:Traslado Base="1422.41" Impuesto="002"
                        TipoFactor="Tasa" TasaOCuota="0.160000"
                        Importe="227.59"/>
                </cfdi:Traslados>
            </cfdi:Impuestos>
        </cfdi:Concepto>"""
        tfd = ""
        if include_tfd:
            uuid_val = tfd_uuid if tfd_uuid is not None else uuid
            uuid_attr = f' UUID="{uuid_val}"' if uuid_val else ""
            fecha_attr = f' FechaTimbrado="{fecha_timbrado}"' if fecha_timbrado else ""
            tfd = f"""
    <cfdi:Complemento>
        <tfd:TimbreFiscalDigital
            xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
            Version="1.1"{uuid_attr}{fecha_attr}
            RfcProvCertif="SPR190613I52"/>
    </cfdi:Complemento>"""
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    Version="4.0"{serie_attr}{folio_attr}
    Fecha="{fecha}"
    FormaPago="04" SubTotal="1422.41" Descuento="0.00"
    Moneda="{moneda}" Total="1650.00" TipoDeComprobante="{tipo}"
    MetodoPago="PUE" Exportacion="01" LugarExpedicion="06600">
    {emisor}
    <cfdi:Receptor Rfc="{RECEPTOR_RFC}"
        Nombre="ESCUELA KEMPER URGATE"
        DomicilioFiscalReceptor="06600"
        RegimenFiscalReceptor="603" UsoCFDI="G03"/>
    <cfdi:Conceptos>
        {conceptos}
    </cfdi:Conceptos>
    {tfd}
</cfdi:Comprobante>"""
        return xml.encode()

    def _tax_node(self, tag="Traslado", **attrs):
        attr_str = " ".join(f'{key}="{value}"' for key, value in attrs.items())
        return etree.fromstring(f"<{tag} {attr_str}/>")

    def _draft_bill_line(self):
        move = (
            self.env["account.move"]
            .with_company(self.company)
            .create(
                {
                    "move_type": "in_invoice",
                    "journal_id": self.journal.id,
                }
            )
        )
        line = self.env["account.move.line"].create(
            {"move_id": move.id, "company_id": self.company.id}
        )
        return move, line

    def _ensure_purchase_tax(self, amount, tax_type="iva", name=None):
        Tax = self.env["account.tax"]
        domain = [
            *Tax._check_company_domain(self.company),
            ("amount", "=", amount),
            ("type_tax_use", "=", "purchase"),
            ("amount_type", "=", "percent"),
        ]
        if "l10n_mx_tax_type" in Tax._fields:
            if tax_type:
                domain.append(("l10n_mx_tax_type", "=", tax_type))
            else:
                domain.append(("l10n_mx_tax_type", "=", False))
        tax = Tax.search(domain, limit=1)
        if tax:
            return tax
        vals = {
            "name": name or f"Test purchase {amount}%",
            "amount": amount,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "company_id": self.company.id,
        }
        if "l10n_mx_tax_type" in Tax._fields and tax_type:
            vals["l10n_mx_tax_type"] = tax_type
        return Tax.create(vals)
