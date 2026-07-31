"""Odoo enrichments for satcfdi Facturama Multiemisor payloads.

``cfdi_to_facturama_payload`` omits fields we need in production:
- ``NameId`` for Egreso/Pago PDF titles (legacy dicts used these)
- Concept ``NumerosPedimento`` from CFDI ``InformacionAduanera`` (COMEX)

When the CFDI includes Complemento Comercio Exterior, Multiemisor cannot map
it; switch to :class:`satcfdi.pacs.facturama.FacturamaWeb` (same credentials).

Cancel responses also discard Facturama ``Message`` when ``Status`` is set;
preserve both so Odoo can show clear cancellation feedback.

Payment / ForeignTrade / Date quirks fixed here (upstream mapper gaps):
- Pago: drop ``ExchangeRate`` for MXN; normalize ``PaymentForm`` to SAT code
- Carta Porte / stamp: refresh stale ``Date`` (SAT 72h window)
- CCE: Facturama expects ``Recipient[].Addresses`` (not ``Address``)
"""

from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timedelta

from satcfdi.cfdi import CFDI
from satcfdi.pacs import Accept, CancelationAcknowledgment, Document, Environment
from satcfdi.utils import iterate

_logger = logging.getLogger(__name__)

# Facturama Catalogs/NameIds — PDF document title. Defaults to "1" (Factura).
_FACTURAMA_NAME_IDS = {
    "I": "1",
    "E": "2",  # Nota de crédito
    "P": "14",  # Complemento de pago
    "T": "1",  # overridden to 36 when Carta Porte complement is present
    "N": "16",
}

_PAYMENT_FORM_RE = re.compile(r"(\d{2})")
# Refresh payload Date when older/newer than this (SAT stamp window is 72h).
_STALE_DATE_HOURS = 60


def enrich_facturama_payload(cfdi: CFDI, payload: dict) -> dict:
    """Fill gaps left by ``cfdi_to_facturama_payload`` for Odoo flows."""
    if not isinstance(payload, dict):
        return payload

    tipo = str(payload.get("CfdiType") or "")
    complemento = payload.get("Complemento") or {}
    has_carta_porte = isinstance(complemento, dict) and bool(
        complemento.get("CartaPorte31")
    )
    if not payload.get("NameId"):
        if tipo == "T" and has_carta_porte:
            payload["NameId"] = "36"
        else:
            payload["NameId"] = _FACTURAMA_NAME_IDS.get(tipo, "1")
    elif tipo == "T" and has_carta_porte and str(payload.get("NameId")) != "36":
        # Carta Porte 3.1 requires NameId 36 (Facturama Multiemisor docs).
        payload["NameId"] = "36"

    # CFDI 4.0 Multiemisor expects Exportation on tipo P. satcfdi's
    # Comprobante.pago keeps Exportacion=01; stripping it yields ASP.NET
    # ModelState "La solicitud no es válida."
    if tipo == "P" and not payload.get("Exportation"):
        payload["Exportation"] = "01"

    if tipo == "P":
        _enrich_payment_complement(payload)

    if isinstance(complemento, dict) and complemento.get("ForeignTrade"):
        _enrich_foreign_trade(complemento["ForeignTrade"])

    _ensure_fresh_date(payload, cfdi)

    items = payload.get("Items")
    if items and isinstance(cfdi, CFDI) and cfdi.get("Conceptos"):
        conceptos = list(iterate(cfdi["Conceptos"]))
        for concepto, item in zip(conceptos, items, strict=False):
            if not isinstance(item, dict) or item.get("NumerosPedimento"):
                continue
            pedimentos = _pedimentos_from_concepto(concepto)
            if pedimentos:
                item["NumerosPedimento"] = pedimentos
    return payload


def _normalize_payment_form(value) -> str | None:
    """Return a SAT c_FormaPago code (``01``..``99``) or None."""
    if value is None or value is False:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"false", "none"}:
        return None
    match = _PAYMENT_FORM_RE.search(text)
    return match.group(1) if match else None


def _enrich_payment_complement(payload: dict) -> None:
    """Fix Multiemisor Pagos ModelState errors on PaymentForm / ExchangeRate."""
    complemento = payload.get("Complemento") or {}
    payments = complemento.get("Payments") if isinstance(complemento, dict) else None
    if not payments:
        return
    for payment in payments:
        if not isinstance(payment, dict):
            continue
        form = _normalize_payment_form(payment.get("PaymentForm"))
        if form:
            payment["PaymentForm"] = form
        currency = str(payment.get("Currency") or "MXN").upper()
        # Facturama: ExchangeRate must not be sent when MonedaP is MXN
        # ("No debe incluir este atributo").
        if currency == "MXN":
            payment.pop("ExchangeRate", None)


def _enrich_foreign_trade(foreign_trade: dict) -> None:
    """Facturama Web expects ``Recipient[].Addresses`` (plural list)."""
    if not isinstance(foreign_trade, dict):
        return
    recipients = foreign_trade.get("Recipient")
    if not recipients:
        # Destinatario omitted (same as receptor): still require Addresses.
        receiver = foreign_trade.get("Receiver") or {}
        addr = receiver.get("Address") if isinstance(receiver, dict) else None
        if addr:
            foreign_trade["Recipient"] = [
                {
                    "Addresses": [addr] if isinstance(addr, dict) else list(addr),
                    **{
                        k: v
                        for k, v in receiver.items()
                        if k not in ("Address", "Addresses")
                    },
                }
            ]
        return
    for entry in recipients:
        if not isinstance(entry, dict):
            continue
        addresses = entry.pop("Addresses", None) or entry.pop("Address", None)
        if not addresses:
            continue
        if isinstance(addresses, dict):
            addresses = [addresses]
        entry["Addresses"] = list(addresses)


def _parse_payload_date(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value).strip().replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:26], fmt)
        except ValueError:
            continue
    return None


def _mexico_now_naive(cfdi=None) -> datetime:
    """Best-effort local stamp time (Mexico when LugarExpedicion is known)."""
    lugar = None
    if cfdi is not None and hasattr(cfdi, "get"):
        try:
            lugar = cfdi.get("LugarExpedicion")
        except Exception:  # noqa: BLE001
            lugar = None
    if lugar:
        try:
            from satcfdi.transform import get_timezone

            return datetime.now(tz=get_timezone(str(lugar))).replace(tzinfo=None)
        except Exception:  # noqa: BLE001
            _logger.debug(
                "Could not resolve timezone for LugarExpedicion=%s",
                lugar,
                exc_info=True,
            )
    return datetime.now()


def _ensure_fresh_date(payload: dict, cfdi=None) -> None:
    """SAT/PAC reject Fecha outside the ~72h stamp window."""
    now = _mexico_now_naive(cfdi)
    current = _parse_payload_date(payload.get("Date"))
    stale = current is None or abs(now - current) > timedelta(hours=_STALE_DATE_HOURS)
    if stale:
        payload["Date"] = now.strftime("%Y-%m-%d %H:%M:%S")


def _pedimentos_from_concepto(concepto) -> list[str]:
    aduanera = None
    if hasattr(concepto, "get"):
        aduanera = concepto.get("InformacionAduanera")
    if not aduanera:
        return []
    numbers = []
    for node in iterate(aduanera):
        if isinstance(node, str):
            text = node.strip()
        elif hasattr(node, "get"):
            text = str(
                node.get("NumeroPedimento") or node.get("NumPedimento") or ""
            ).strip()
        else:
            text = str(node).strip()
        if text:
            numbers.append(text)
    return numbers


def _is_mock(value) -> bool:
    return type(value).__module__.startswith("unittest.mock")


def cfdi_has_comercio_exterior(cfdi) -> bool:
    """Return True when the CFDI carries a ComercioExterior complement."""
    if cfdi is None or _is_mock(cfdi):
        return False
    try:
        complemento = cfdi.get("Complemento") if hasattr(cfdi, "get") else None
    except Exception:  # noqa: BLE001 - defensive for odd CFDI shapes
        return False
    # Empty dict/list complements are falsy; use identity checks so a bare
    # ComercioExterior node (dict subclass) is still detected.
    if complemento is None or _is_mock(complemento):
        return False
    if "ComercioExterior" in type(complemento).__name__:
        return True
    if hasattr(complemento, "tag") and "ComercioExterior" in str(complemento.tag):
        return True
    if hasattr(complemento, "get"):
        try:
            node = complemento.get("ComercioExterior")
        except Exception:  # noqa: BLE001
            node = None
        if node is not None and not _is_mock(node):
            return True
    for node in iterate(complemento):
        if _is_mock(node):
            continue
        tag = getattr(node, "tag", None) or ""
        if "ComercioExterior" in str(tag):
            return True
        if "ComercioExterior" in type(node).__name__:
            return True
    return False


def build_facturama_web(service):
    """Instantiate FacturamaWeb with the same credentials as Multiemisor."""
    from satcfdi.pacs.facturama import FacturamaWeb

    environment = Environment.TEST if service.sandbox_mode else Environment.PRODUCTION
    pac = FacturamaWeb(
        username=service.user,
        password=service.password,
        environment=environment,
    )
    return bind_enriched_issue(bind_enriched_cancel(pac))


def ensure_facturama_pac_for_cfdi(pac, service, cfdi):
    """Use FacturamaWeb when the CFDI includes Comercio Exterior.

    Multiemisor rejects CCE (``_allow_foreign_trade=False``). API Web supports
    it with the same user/password; CSD must already live on the Facturama
    account profile (not Multiemisor upload).
    """
    if not cfdi_has_comercio_exterior(cfdi):
        return pac
    if getattr(pac, "_allow_foreign_trade", False):
        return pac
    _logger.info(
        "CFDI includes ComercioExterior; switching Facturama Multiemisor "
        "to FacturamaWeb for issue()"
    )
    return build_facturama_web(service)


def bind_enriched_issue(pac):
    """Replace ``pac.issue`` with a version that enriches the JSON payload."""
    from satcfdi.pacs.facturama import cfdi_to_facturama_payload

    def issue(cfdi: CFDI, accept: Accept = Accept.XML) -> Document:
        allow_ft = getattr(pac, "_allow_foreign_trade", False)
        if cfdi_has_comercio_exterior(cfdi) and not allow_ft:
            # Surfaced by cfdi.service.create_cfdi as a translated UserError.
            raise NotImplementedError(
                "Facturama Multiemisor does not support Comercio Exterior; "
                "use FacturamaWeb (API Web)."
            )
        payload = cfdi_to_facturama_payload(
            cfdi,
            allow_foreign_trade=allow_ft,
        )
        enrich_facturama_payload(cfdi, payload)
        created = pac._request("post", pac._issue_path, json=payload)
        document_id = created["Id"]

        xml = None
        pdf = None
        if accept & Accept.XML:
            xml = pac._download_file(document_id, "xml")
        if accept & Accept.PDF:
            pdf = pac._download_file(document_id, "pdf")
        return Document(document_id=document_id, xml=xml, pdf=pdf)

    pac.issue = issue
    return pac


def _decode_acuse_content(content):
    if content is None or content is False:
        return None
    if isinstance(content, (bytes, bytearray)):
        return bytes(content) or None
    if isinstance(content, str):
        if not content.strip():
            return None
        try:
            return base64.b64decode(content)
        except Exception:  # noqa: BLE001 - PAC payloads vary
            return content.encode()
    return None


def _fetch_facturama_acuse(pac, facturama_id: str):
    """GET /acuse/{format}/{type}/{id} when DELETE omitted AcuseXmlBase64."""
    cfdi_type = (
        "issuedLite"
        if getattr(pac, "_download_type", None) == "issuedLite"
        else "issued"
    )
    for fmt in ("xml", "pdf"):
        for path in (
            f"acuse/{fmt}/{cfdi_type}/{facturama_id}",
            f"api/Acuse/{fmt}/{cfdi_type}/{facturama_id}",
        ):
            try:
                res = pac._request("get", path)
            except Exception:  # noqa: BLE001 - endpoint may 404
                _logger.debug(
                    "Facturama acuse fetch failed for %s (%s)", facturama_id, path
                )
                continue
            if isinstance(res, dict):
                content = (
                    res.get("Content") or res.get("AcuseXmlBase64") or res.get("Acuse")
                )
                acuse = _decode_acuse_content(content)
                if acuse:
                    # Content from /acuse is urlsafe base64 in satcfdi downloads
                    if isinstance(content, str) and "Content" in res:
                        try:
                            acuse = base64.urlsafe_b64decode(content.encode("utf-8"))
                        except Exception:  # noqa: BLE001
                            _logger.debug(
                                "urlsafe acuse decode failed; using std decode",
                                exc_info=True,
                            )
                    return acuse
            elif isinstance(res, (bytes, bytearray)) and res:
                return bytes(res)
    return None


def bind_enriched_cancel(pac):
    """Wrap ``pac.cancel`` so Facturama Status + Message are both preserved.

    Upstream satcfdi stores only ``Status or Message`` in
    ``CancelationAcknowledgment.code``, dropping the human-readable Message
    when Status is present. Odoo needs both for post-cancel feedback.

    When ``AcuseXmlBase64`` is empty (common when cancel is still pending or
    SAT-direct), try Facturama's GET acuse endpoint before giving up.
    """

    def cancel(
        cfdi: CFDI,
        reason,
        substitution_id=None,
        signer=None,
        document_id=None,
    ) -> CancelationAcknowledgment:
        del signer  # Facturama cancels with account credentials, not local FIEL
        if document_id:
            facturama_id = document_id
        else:
            uuid = cfdi["Complemento"]["TimbreFiscalDigital"]["UUID"]
            facturama_id = pac.find_id_by_uuid(uuid)

        params = {"motive": getattr(reason, "value", reason)}
        if substitution_id:
            params["uuidReplacement"] = substitution_id
        if getattr(pac, "_cancel_path_prefix", None) == "api/Cfdi":
            params["type"] = "issued"

        res = pac._request(
            "delete",
            f"{pac._cancel_path_prefix}/{facturama_id}",
            params=params,
        )
        acuse = None
        status = None
        message = None
        if isinstance(res, dict):
            status = res.get("Status")
            message = res.get("Message")
            acuse = _decode_acuse_content(res.get("AcuseXmlBase64") or res.get("Acuse"))
            if status or message:
                code = {"Status": status, "Message": message}
            else:
                code = "cancelled"
        else:
            code = "cancelled"

        if not acuse and facturama_id:
            acuse = _fetch_facturama_acuse(pac, facturama_id)
            if not acuse and isinstance(code, dict) and not code.get("Message"):
                code["Message"] = (
                    "Cancellation accepted by Facturama, but no acuse XML was "
                    "returned (common when cancel is pending acceptance or "
                    "processed directly with the SAT)."
                )

        return CancelationAcknowledgment(code=code, acuse=acuse)

    pac.cancel = cancel
    return pac
