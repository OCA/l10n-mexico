"""Helpers to map Odoo CFDI intermediate data to satcfdi cfdi40 objects."""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from satcfdi.create.cfd import cfdi40

# SAT c_TasaOCuota values are expressed with 6 decimal places (e.g. 0.160000).
_TASA_QUANT = Decimal("0.000001")


def _dec(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _dec_tasa(value) -> Decimal:
    """Quantize a tax rate for CFDI TasaOCuota (6 decimal places)."""
    return _dec(value).quantize(_TASA_QUANT, rounding=ROUND_HALF_UP)


def _parse_fecha(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def tax_code_from_name(name: str) -> str:
    return {"ISR": "001", "IVA": "002", "IEPS": "003"}.get(name, name or "002")


def build_concepto_impuestos(taxes: list[dict] | None):
    if not taxes:
        return None
    traslados = []
    retenciones = []
    for tax in taxes:
        payload = {
            "impuesto": tax_code_from_name(tax.get("Name")),
            "tipo_factor": "Tasa",
            "tasa_o_cuota": _dec_tasa(tax.get("Rate")),
            "base": _dec(tax.get("Base")),
            "importe": _dec(tax.get("Total")),
        }
        if tax.get("IsRetention"):
            retenciones.append(cfdi40.Retencion(**payload))
        else:
            traslados.append(cfdi40.Traslado(**payload))
    return cfdi40.Impuestos(
        traslados=traslados or None,
        retenciones=retenciones or None,
    )


def build_concepto_from_item(item: dict) -> cfdi40.Concepto:
    impuestos = build_concepto_impuestos(item.get("Taxes"))
    kwargs = {
        "clave_prod_serv": item["ProductCode"],
        "cantidad": _dec(item.get("Quantity")),
        "clave_unidad": item["UnitCode"],
        "descripcion": item.get("Description") or "",
        "valor_unitario": _dec(item.get("UnitPrice")),
        "objeto_imp": item.get("TaxObject") or "01",
    }
    if item.get("IdentificationNumber"):
        kwargs["no_identificacion"] = item["IdentificationNumber"]
    if item.get("Discount"):
        discount = _dec(item["Discount"])
        if discount:
            kwargs["descuento"] = discount
    if impuestos is not None:
        kwargs["impuestos"] = impuestos
    if item.get("NumerosPedimento"):
        # InformacionAduanera expects pedimento numbers as sequence of strings
        kwargs["informacion_aduanera"] = list(item["NumerosPedimento"])
    return cfdi40.Concepto(**kwargs)


def build_receptor(receiver: dict) -> cfdi40.Receptor:
    return cfdi40.Receptor(
        rfc=receiver["Rfc"],
        nombre=receiver["Name"],
        domicilio_fiscal_receptor=receiver.get("TaxZipCode") or "",
        regimen_fiscal_receptor=receiver["FiscalRegime"],
        uso_cfdi=receiver["CfdiUse"],
    )


def build_emisor(issuer) -> cfdi40.Emisor:
    return cfdi40.Emisor(
        rfc=issuer.vat,
        nombre=issuer.fiscal_name or issuer.name,
        regimen_fiscal=issuer.tax_regime.code,
    )


def build_informacion_global(info: dict | None):
    if not info:
        return None
    return cfdi40.InformacionGlobal(
        periodicidad=info["Periodicity"],
        meses=info["Months"],
        ano=int(info["Year"]),
    )


def build_comprobante(
    *,
    issuer,
    receiver: dict,
    conceptos: list[dict],
    tipo_de_comprobante: str,
    lugar_expedicion: str,
    moneda: str = "MXN",
    serie: str | None = None,
    folio: str | None = None,
    forma_pago: str | None = None,
    metodo_pago: str | None = None,
    fecha=None,
    informacion_global: dict | None = None,
    cfdi_relacionados=None,
    complemento=None,
    exportacion: str | None = "01",
) -> cfdi40.Comprobante:
    kwargs = {
        "emisor": build_emisor(issuer),
        "lugar_expedicion": lugar_expedicion,
        "receptor": build_receptor(receiver),
        "conceptos": [build_concepto_from_item(item) for item in conceptos],
        "moneda": moneda,
        "tipo_de_comprobante": tipo_de_comprobante,
        "serie": serie,
        "folio": folio,
        "forma_pago": forma_pago,
        "metodo_pago": metodo_pago,
        "fecha": _parse_fecha(fecha),
        "informacion_global": build_informacion_global(informacion_global),
        "cfdi_relacionados": cfdi_relacionados,
        "complemento": complemento,
    }
    # satcfdi defaults Exportacion to "01". Callers may pass None to omit it
    # for PACs that reject the attribute (not Facturama Multiemisor tipo P —
    # that path needs Exportacion=01).
    if exportacion is not None:
        kwargs["exportacion"] = exportacion
    cfdi = cfdi40.Comprobante(**kwargs)
    if exportacion is None:
        cfdi.pop("Exportacion", None)
    return cfdi
