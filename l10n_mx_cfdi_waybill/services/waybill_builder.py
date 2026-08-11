"""Build satcfdi Comprobante + Carta Porte 3.1 from waybill dict payloads."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from satcfdi.create.cfd import cartaporte31 as cp
from satcfdi.create.cfd import cfdi40

from odoo.addons.l10n_mx_cfdi.services import cfdi_builder

_logger = logging.getLogger(__name__)


def _dec(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _parse_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value).replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return datetime.now()


def _new_id_ccp() -> str:
    # SAT IdCCP: 36 chars, CCC prefix + RFC4122-shaped remainder.
    return ("CCC" + str(uuid.uuid4())[3:])[:36]


def _build_domicilio(data: dict | None):
    if not data:
        return None
    kwargs = {
        "pais": data.get("Pais"),
        "codigo_postal": data.get("CodigoPostal"),
        "estado": data.get("Estado"),
        "municipio": data.get("Municipio") or None,
        "localidad": data.get("Localidad") or None,
        "colonia": data.get("Colonia") or None,
        "calle": data.get("Calle") or None,
        "numero_exterior": data.get("NumeroExterior") or None,
        "numero_interior": data.get("NumeroInterior") or None,
        "referencia": data.get("Referencia") or None,
    }
    kwargs = {k: v for k, v in kwargs.items() if v not in (None, "")}
    return cp.Domicilio(**kwargs) if kwargs.get("pais") else None


def _build_ubicaciones(locations: list[dict]):
    ubicaciones = []
    for loc in locations or []:
        kwargs = {
            "tipo_ubicacion": loc["TipoUbicacion"],
            "rfc_remitente_destinatario": loc["RFCRemitenteDestinatario"],
            "fecha_hora_salida_llegada": _parse_dt(loc["FechaHoraSalidaLlegada"]),
            "id_ubicacion": loc.get("IDUbicacion"),
            "domicilio": _build_domicilio(loc.get("Domicilio")),
        }
        if loc.get("DistanciaRecorrida") not in (None, "", 0, "0"):
            kwargs["distancia_recorrida"] = _dec(loc["DistanciaRecorrida"])
        ubicaciones.append(cp.Ubicacion(**kwargs))
    return ubicaciones


def _build_mercancia(goods: list[dict]):
    mercancias = []
    for item in goods or []:
        cantidad_transporta = None
        ct_list = item.get("CantidadTransporta") or []
        if ct_list:
            cantidad_transporta = [
                cp.CantidadTransporta(
                    cantidad=_dec(ct["Cantidad"]),
                    id_origen=ct["IDOrigen"],
                    id_destino=ct["IDDestino"],
                )
                for ct in ct_list
            ]
        mercancias.append(
            cp.Mercancia(
                bienes_transp=item["BienesTransp"],
                descripcion=item["Descripcion"],
                cantidad=_dec(item["Cantidad"]),
                clave_unidad=item["ClaveUnidad"],
                peso_en_kg=_dec(item["PesoEnKg"]),
                cantidad_transporta=cantidad_transporta,
            )
        )
    return mercancias


def _build_autotransporte(auto: dict | None):
    if not auto:
        return None
    veh = auto.get("IdentificacionVehicular") or {}
    seg = auto.get("Seguros") or {}
    return cp.Autotransporte(
        perm_sct=auto["PermSCT"],
        num_permiso_sct=auto["NumPermisoSCT"],
        identificacion_vehicular=cp.IdentificacionVehicular(
            config_vehicular=veh["ConfigVehicular"],
            placa_vm=veh["PlacaVM"],
            anio_modelo_vm=int(veh["AnioModeloVM"]),
            peso_bruto_vehicular=_dec(veh["PesoBrutoVehicular"]),
        ),
        seguros=cp.Seguros(
            asegura_resp_civil=seg["AseguraRespCivil"],
            poliza_resp_civil=seg["PolizaRespCivil"],
        ),
    )


def _build_figura_transporte(figuras: list[dict] | None):
    if not figuras:
        return None
    result = []
    for fig in figuras:
        kwargs = {
            "tipo_figura": fig["TipoFigura"],
            "rfc_figura": fig.get("RFCFigura"),
            "nombre_figura": fig.get("NombreFigura"),
            "num_licencia": fig.get("NumLicencia"),
        }
        partes = fig.get("PartesTransporte")
        if partes:
            kwargs["partes_transporte"] = [
                p.get("ParteTransporte") if isinstance(p, dict) else p for p in partes
            ]
        kwargs = {k: v for k, v in kwargs.items() if v not in (None, "", [])}
        result.append(cp.TiposFigura(**kwargs))
    return result


def build_carta_porte_from_dict(cp_data: dict) -> cp.CartaPorte:
    mercancias_data = cp_data.get("Mercancias") or {}
    goods = mercancias_data.get("Mercancia") or []
    if isinstance(goods, dict):
        goods = [goods]
    locations = cp_data.get("Ubicaciones") or []
    total_dist = sum(
        _dec(loc.get("DistanciaRecorrida") or 0)
        for loc in locations
        if loc.get("TipoUbicacion") == "Destino"
    )
    peso_total = sum(_dec(g.get("PesoEnKg") or 0) for g in goods)
    mercancias = cp.Mercancias(
        peso_bruto_total=peso_total or Decimal("0.001"),
        unidad_peso=mercancias_data.get("UnidadPeso") or "KGM",
        num_total_mercancias=len(goods) or 1,
        mercancia=_build_mercancia(goods),
        autotransporte=_build_autotransporte(mercancias_data.get("Autotransporte")),
    )
    kwargs = {
        "id_ccp": cp_data.get("IdCCP") or _new_id_ccp(),
        "transp_internac": cp_data.get("TranspInternac") or "No",
        "ubicaciones": _build_ubicaciones(locations),
        "mercancias": mercancias,
        "figura_transporte": _build_figura_transporte(cp_data.get("FiguraTransporte")),
    }
    if total_dist:
        kwargs["total_dist_rec"] = total_dist
    return cp.CartaPorte(**kwargs)


def _mexico_city_now_naive() -> datetime:
    """Naive local time in America/Mexico_City (SAT stamp window)."""
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/Mexico_City")).replace(tzinfo=None)
    except Exception:  # noqa: BLE001 - never use host TZ as Mexico local
        return datetime.utcnow()


def _stamp_fecha(lugar_expedicion: str | None = None) -> datetime:
    """Current CFDI Fecha in Mexico local time for the expedition place.

    Never returns a time ahead of America/Mexico_City "now" (Runboat/UTC hosts
    otherwise emit a future Fecha that Facturama/SAT reject within the 72h
    window). A small skew buffer absorbs PAC clock differences.
    """
    mx_now = _mexico_city_now_naive()
    stamp = mx_now
    if lugar_expedicion:
        try:
            from satcfdi.transform import get_timezone

            stamp = datetime.now(tz=get_timezone(str(lugar_expedicion))).replace(
                tzinfo=None
            )
        except Exception:  # noqa: BLE001 - fall back to Mexico City
            _logger.debug(
                "Could not resolve timezone for LugarExpedicion=%s",
                lugar_expedicion,
                exc_info=True,
            )
            stamp = mx_now
    if stamp > mx_now:
        stamp = mx_now
    return stamp - timedelta(seconds=30)


def build_waybill_comprobante(issuer, data: dict) -> cfdi40.Comprobante:
    """Map waybill ``_format_data()`` dict to a stampable satcfdi Comprobante."""
    cp_data = (data.get("Complemento") or {}).get("CartaPorte31") or {}
    carta = build_carta_porte_from_dict(cp_data)
    receiver = data["Receiver"]
    receiver_rfc = receiver["Rfc"]
    receiver_data = {
        "Name": receiver["Name"],
        "Rfc": receiver_rfc,
        "CfdiUse": receiver["CfdiUse"],
        "FiscalRegime": receiver["FiscalRegime"],
        "TaxZipCode": receiver["TaxZipCode"],
    }
    lugar = data["ExpeditionPlace"]
    # Stamp-time Fecha (Mexico TZ). Stale create dates fail Facturama/SAT 72h.
    fecha = _stamp_fecha(lugar)
    # CFDI 4.0 requires InformacionGlobal for público en general / extranjero.
    informacion_global = None
    if receiver_rfc in ("XAXX010101000", "XEXX010101000"):
        informacion_global = {
            "Periodicity": "01",
            "Months": str(fecha.month).rjust(2, "0"),
            "Year": fecha.year,
        }
        receiver_data["FiscalRegime"] = "616"
        receiver_data["TaxZipCode"] = data.get("ExpeditionPlace") or receiver_data.get(
            "TaxZipCode"
        )
    return cfdi_builder.build_comprobante(
        issuer=issuer,
        receiver=receiver_data,
        conceptos=data.get("Items") or [],
        tipo_de_comprobante=data.get("CfdiType") or "T",
        lugar_expedicion=lugar,
        complemento=carta,
        exportacion="01",
        serie=data.get("Serie"),
        folio=data.get("Folio"),
        fecha=fecha,
        informacion_global=informacion_global,
    )
