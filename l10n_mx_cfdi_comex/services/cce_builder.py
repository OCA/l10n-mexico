"""Build satcfdi ``cce20.ComercioExterior`` from invoice / dict payloads."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from satcfdi.create.cfd import cce20


def _dec(value, quant="0.01") -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal(quant), rounding=ROUND_HALF_UP)


def _dec6(value) -> Decimal:
    return _dec(value, quant="0.000001")


def build_domicilio(data: dict | None) -> cce20.Domicilio | None:
    """Build a CCE ``Domicilio`` from a flat address dict."""
    if not data:
        return None
    calle = data.get("Calle") or data.get("calle")
    estado = data.get("Estado") or data.get("estado")
    pais = data.get("Pais") or data.get("pais")
    codigo_postal = data.get("CodigoPostal") or data.get("codigo_postal")
    if not all([calle, estado, pais, codigo_postal]):
        return None
    kwargs = {
        "calle": calle,
        "estado": estado,
        "pais": pais,
        "codigo_postal": codigo_postal,
        "numero_exterior": data.get("NumeroExterior") or data.get("numero_exterior"),
        "numero_interior": data.get("NumeroInterior") or data.get("numero_interior"),
        "colonia": data.get("Colonia") or data.get("colonia"),
        "localidad": data.get("Localidad") or data.get("localidad"),
        "referencia": data.get("Referencia") or data.get("referencia"),
        "municipio": data.get("Municipio") or data.get("municipio"),
    }
    kwargs = {k: v for k, v in kwargs.items() if v not in (None, "")}
    return cce20.Domicilio(**kwargs)


def build_mercancia(items: list[dict]) -> list[cce20.Mercancia]:
    mercancias = []
    for item in items or []:
        kwargs = {
            "no_identificacion": item["NoIdentificacion"],
            "valor_dolares": _dec(item["ValorDolares"]),
        }
        if item.get("FraccionArancelaria"):
            kwargs["fraccion_arancelaria"] = item["FraccionArancelaria"]
        if item.get("CantidadAduana") is not None:
            kwargs["cantidad_aduana"] = _dec(item["CantidadAduana"], quant="0.001")
        if item.get("UnidadAduana"):
            kwargs["unidad_aduana"] = item["UnidadAduana"]
        if item.get("ValorUnitarioAduana") is not None:
            kwargs["valor_unitario_aduana"] = _dec6(item["ValorUnitarioAduana"])
        mercancias.append(cce20.Mercancia(**kwargs))
    return mercancias


def build_comercio_exterior(data: dict) -> cce20.ComercioExterior:
    """Build ``ComercioExterior`` 2.0 from a structured dict."""
    mercancias = data.get("Mercancias") or data.get("mercancias") or []
    if isinstance(mercancias, dict):
        mercancias = [mercancias]

    emisor = None
    emisor_data = data.get("Emisor") or data.get("emisor")
    if emisor_data:
        domicilio = build_domicilio(
            emisor_data.get("Domicilio") or emisor_data.get("domicilio") or emisor_data
        )
        if domicilio:
            emisor = cce20.Emisor(
                domicilio=domicilio,
                curp=emisor_data.get("Curp") or emisor_data.get("curp"),
            )

    receptor = None
    receptor_data = data.get("Receptor") or data.get("receptor")
    if receptor_data:
        domicilio = build_domicilio(
            receptor_data.get("Domicilio")
            or receptor_data.get("domicilio")
            or receptor_data
        )
        receptor = cce20.Receptor(
            num_reg_id_trib=receptor_data.get("NumRegIdTrib")
            or receptor_data.get("num_reg_id_trib"),
            domicilio=domicilio,
        )

    destinatario = None
    dest_data = data.get("Destinatario") or data.get("destinatario")
    if dest_data:
        domicilio = build_domicilio(
            dest_data.get("Domicilio") or dest_data.get("domicilio") or dest_data
        )
        if domicilio:
            destinatario = cce20.Destinatario(
                domicilio=domicilio,
                num_reg_id_trib=dest_data.get("NumRegIdTrib")
                or dest_data.get("num_reg_id_trib"),
                nombre=dest_data.get("Nombre") or dest_data.get("nombre"),
            )

    kwargs = {
        "clave_de_pedimento": data.get("ClaveDePedimento")
        or data.get("clave_de_pedimento"),
        "certificado_origen": int(
            data.get("CertificadoOrigen", data.get("certificado_origen", 0))
        ),
        "tipo_cambio_usd": _dec6(
            data.get("TipoCambioUSD") or data.get("tipo_cambio_usd")
        ),
        "total_usd": _dec(data.get("TotalUSD") or data.get("total_usd")),
        "mercancias": build_mercancia(mercancias),
        "incoterm": data.get("Incoterm") or data.get("incoterm"),
        "observaciones": data.get("Observaciones") or data.get("observaciones"),
        "motivo_traslado": data.get("MotivoTraslado") or data.get("motivo_traslado"),
        "num_certificado_origen": data.get("NumCertificadoOrigen")
        or data.get("num_certificado_origen"),
        "numero_exportador_confiable": data.get("NumeroExportadorConfiable")
        or data.get("numero_exportador_confiable"),
        "emisor": emisor,
        "receptor": receptor,
        "destinatario": destinatario,
    }
    kwargs = {k: v for k, v in kwargs.items() if v not in (None, "", [])}
    return cce20.ComercioExterior(**kwargs)


def build_comercio_exterior_from_invoice(invoice) -> cce20.ComercioExterior:
    """Gather CCE data from an ``account.move`` with COMEX fields enabled."""
    return build_comercio_exterior(invoice._l10n_mx_cfdi_cce_gather_data())
