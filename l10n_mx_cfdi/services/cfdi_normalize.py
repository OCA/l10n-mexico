"""Normalize satcfdi PAC results into a stable dict for Odoo documents."""

from __future__ import annotations

import base64
import logging
from typing import Any

from lxml import etree
from satcfdi.cfdi import CFDI
from satcfdi.pacs import Document as PacDocument

_logger = logging.getLogger(__name__)

TFD_NS = "http://www.sat.gob.mx/TimbreFiscalDigital"
CFDI_NS = "http://www.sat.gob.mx/cfd/4"


def _extract_stamp_meta_from_xml_bytes(xml: bytes) -> dict[str, Any]:
    """Best-effort Timbre/Comprobante extraction via lxml (for incomplete XML)."""
    root = etree.fromstring(xml)
    ns = {"cfdi": CFDI_NS, "tfd": TFD_NS}
    timbre = root.find(
        ".//{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital"
    )
    if timbre is None:
        timbre = root.find(".//tfd:TimbreFiscalDigital", namespaces=ns)

    def _attr(node, name, default=""):
        return node.get(name, default) if node is not None else default

    total = root.get("Total") or "0"
    sello = root.get("Sello") or _attr(timbre, "SelloCFD")
    return {
        "Date": root.get("Fecha") or "",
        "CertNumber": root.get("NoCertificado") or "",
        "OriginalString": "",
        "Total": str(total),
        "Taxes": [],
        "Complement": {
            "TaxStamp": {
                "Uuid": _attr(timbre, "UUID"),
                "CfdiSign": sello,
                "SatSign": _attr(timbre, "SelloSAT"),
                "SatCertNumber": _attr(timbre, "NoCertificadoSAT"),
                "RfcProvCertif": _attr(timbre, "RfcProvCertif"),
                "Date": _attr(timbre, "FechaTimbrado"),
            }
        },
    }


def _resolve_cadena_original(cfdi) -> str:
    """Return cadena original as a plain string (never a bound method).

    satcfdi exposes ``cadena_original`` as a callable; storing the method itself
    in ``stamp_meta`` makes ``json.dumps`` fail after a successful stamp.
    """
    value = getattr(cfdi, "cadena_original", None)
    if value is None and hasattr(cfdi, "get"):
        value = cfdi.get("OriginalString") or cfdi.get("cadena_original") or ""
    if callable(value):
        try:
            value = value()
        except Exception:  # noqa: BLE001 - PAC/CFDI helpers vary widely
            value = ""
    return str(value or "")


def extract_stamp_meta(cfdi: CFDI) -> dict[str, Any]:
    """Build the JSON metadata used by CFDI document computed fields / QWeb."""
    timbre = cfdi.get("Complemento", {}).get("TimbreFiscalDigital", {})
    total = cfdi.get("Total", "0")
    sello = cfdi.get("Sello") or timbre.get("SelloCFD") or ""
    taxes_meta = []
    impuestos = cfdi.get("Impuestos") or {}
    for traslado in impuestos.get("Traslados") or []:
        taxes_meta.append(
            {
                "Name": _tax_name(traslado.get("Impuesto")),
                "Rate": float(traslado.get("TasaOCuota") or 0),
                "IsRetention": False,
                "Base": float(traslado.get("Base") or 0),
                "Total": float(traslado.get("Importe") or 0),
            }
        )
    for retencion in impuestos.get("Retenciones") or []:
        taxes_meta.append(
            {
                "Name": _tax_name(retencion.get("Impuesto")),
                "Rate": float(retencion.get("TasaOCuota") or 0),
                "IsRetention": True,
                "Base": float(retencion.get("Base") or 0),
                "Total": float(retencion.get("Importe") or 0),
            }
        )

    return {
        "Date": str(cfdi.get("Fecha") or ""),
        "CertNumber": str(cfdi.get("NoCertificado") or ""),
        "OriginalString": _resolve_cadena_original(cfdi),
        "Total": str(total),
        "Taxes": taxes_meta,
        "Complement": {
            "TaxStamp": {
                "Uuid": timbre.get("UUID") or "",
                "CfdiSign": sello,
                "SatSign": timbre.get("SelloSAT") or "",
                "SatCertNumber": timbre.get("NoCertificadoSAT") or "",
                "RfcProvCertif": timbre.get("RfcProvCertif") or "",
                "Date": str(timbre.get("FechaTimbrado") or ""),
            }
        },
    }


def _tax_name(code: str | None) -> str:
    return {"001": "ISR", "002": "IVA", "003": "IEPS"}.get(
        str(code or ""), str(code or "")
    )


def normalize_pac_document(document: PacDocument) -> dict[str, Any]:
    """Convert a satcfdi PAC Document into the shape consumed by document.publish."""
    xml = document.xml or b""
    stamp_meta: dict[str, Any] = {}
    if xml:
        try:
            cfdi = CFDI.from_string(xml)
            stamp_meta = extract_stamp_meta(cfdi)
        except Exception:
            _logger.debug(
                "satcfdi CFDI.from_string failed; falling back to lxml parse",
                exc_info=True,
            )
            try:
                stamp_meta = _extract_stamp_meta_from_xml_bytes(xml)
            except Exception:
                _logger.exception("Unable to parse stamped CFDI XML")
                stamp_meta = {}

    uuid = (
        stamp_meta.get("Complement", {}).get("TaxStamp", {}).get("Uuid")
        or document.document_id
        or ""
    )
    return {
        "status": "published",
        "uuid": uuid,
        "tracking_id": document.document_id or uuid,
        "xml": xml,
        "pdf": document.pdf,
        "stamp_meta": stamp_meta,
    }


def decode_binary_field(value) -> bytes:
    """Decode an Odoo Binary field (base64 str/bytes) to raw bytes."""
    if value is None:
        return b""
    if isinstance(value, bytes):
        try:
            return base64.b64decode(value, validate=True)
        except Exception:
            return value
    if isinstance(value, str):
        return base64.b64decode(value)
    return bytes(value)
