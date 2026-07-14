# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging

from lxml.etree import QName

_logger = logging.getLogger(__name__)

try:
    from satcfdi.models import Signer
    from satcfdi.pacs.sat import (
        SAT,
        EstadoComprobante,
        TipoDescargaMasivaTerceros,
    )

except ImportError as err:
    _logger.debug(err)

    class _MissingSatcfdi:
        """Placeholder so tests can patch Signer/SAT without AttributeError."""

        @staticmethod
        def load(*args, **kwargs):
            raise ImportError(
                "The satcfdi library is required. Install it with: pip install satcfdi"
            )

    class _EstadoComprobante:
        VIGENTE = "Vigente"

    class _TipoDescarga:
        METADATA = type("EnumVal", (), {"value": "Metadata"})()
        CFDI = type("EnumVal", (), {"value": "CFDI"})()

    Signer = _MissingSatcfdi
    SAT = _MissingSatcfdi
    EstadoComprobante = _EstadoComprobante
    TipoDescargaMasivaTerceros = _TipoDescarga


class SatClient:
    """SAT web service adapter via satcfdi.

    Pure Python class with no Odoo ORM dependency.
    Swappable through the res.company.l10n_mx_sat_get_client() factory.
    """

    DOCUMENT_KIND_CFDI = "cfdi"
    DOCUMENT_KIND_RETENTION = "retention"
    DIRECTION_ISSUED = "issued"
    DIRECTION_RECEIVED = "received"
    REQUEST_TYPE_XML = "xml"
    REQUEST_TYPE_METADATA = "metadata"

    _REQUEST_METHODS = {
        (DOCUMENT_KIND_CFDI, DIRECTION_ISSUED): "recover_comprobante_emitted_request",
        (
            DOCUMENT_KIND_CFDI,
            DIRECTION_RECEIVED,
        ): "recover_comprobante_received_request",
        (
            DOCUMENT_KIND_RETENTION,
            DIRECTION_ISSUED,
        ): "recover_retencion_emitted_request",
        (
            DOCUMENT_KIND_RETENTION,
            DIRECTION_RECEIVED,
        ): "recover_retencion_received_request",
    }
    _STATUS_METHODS = {
        DOCUMENT_KIND_CFDI: "recover_comprobante_status",
        DOCUMENT_KIND_RETENTION: "recover_retencion_status",
    }
    _DOWNLOAD_METHODS = {
        DOCUMENT_KIND_CFDI: "recover_comprobante_download",
        DOCUMENT_KIND_RETENTION: "recover_retencion_download",
    }
    _LEGACY_RETENTION_REQUEST = "recover_retencion_request"
    _MIN_SATCFDI_RETENTION = "26.7.2"

    def __init__(self, cer_der, key_der, password):
        """Initialize the client with FIEL credentials."""
        signer = Signer.load(
            certificate=cer_der,
            key=key_der,
            password=password,
        )
        self._sat = SAT(signer=signer)
        self.rfc = signer.rfc

    def authenticate(self):
        """Authenticate with the SAT and return the token."""
        token_data = self._sat._autentica_comprobante()
        token = token_data.get("AutenticaResult")
        if not token:
            raise ValueError("SAT returned an empty token.")
        return token

    def request_download(
        self,
        token,
        rfc,
        date_from,
        date_to,
        document_kind=DOCUMENT_KIND_CFDI,
        direction=DIRECTION_RECEIVED,
        request_type=REQUEST_TYPE_XML,
        **kwargs,
    ):
        """Send a download request to the SAT (Descarga Masiva)."""
        self._ensure_token(token)
        method_name = self._REQUEST_METHODS[(document_kind, direction)]
        method = self._get_sat_method(method_name, document_kind=document_kind)

        tipo_solicitud = self._resolve_tipo_solicitud(request_type)
        request_kwargs = {
            "fecha_inicial": date_from,
            "fecha_final": date_to,
            "tipo_solicitud": tipo_solicitud,
        }

        if document_kind == self.DOCUMENT_KIND_CFDI:
            if direction == self.DIRECTION_ISSUED:
                request_kwargs["rfc_emisor"] = kwargs.pop("rfc_emisor", rfc)
            else:
                request_kwargs["rfc_receptor"] = kwargs.pop("rfc_receptor", rfc)
            for key, value in (
                ("tipo_comprobante", kwargs.pop("tipo_comprobante", None)),
                ("rfc_a_cuenta_terceros", kwargs.pop("rfc_a_cuenta_terceros", None)),
                ("complemento", kwargs.pop("complemento", None)),
            ):
                if value is not None:
                    request_kwargs[key] = value
            if request_type == self.REQUEST_TYPE_XML:
                voucher_status = (
                    kwargs.pop("estado_comprobante", None) or EstadoComprobante.VIGENTE
                )
                request_kwargs["estado_comprobante"] = voucher_status
        elif document_kind == self.DOCUMENT_KIND_RETENTION:
            if direction == self.DIRECTION_ISSUED:
                request_kwargs["rfc_emisor"] = kwargs.pop("rfc_emisor", rfc)
            else:
                request_kwargs["rfc_receptor"] = kwargs.pop("rfc_receptor", rfc)
            complemento = kwargs.pop("complemento", None)
            if complemento is not None:
                request_kwargs["complemento"] = complemento
            if request_type == self.REQUEST_TYPE_XML:
                voucher_status = (
                    kwargs.pop("estado_comprobante", None) or EstadoComprobante.VIGENTE
                )
                request_kwargs["estado_comprobante"] = voucher_status

        request_kwargs = {
            key: value
            for key, value in request_kwargs.items()
            if value is not None and value is not False
        }

        response = method(**request_kwargs)
        return self._normalize_request_response(response)

    def verify_download(
        self, token, rfc, sat_request_id, document_kind=DOCUMENT_KIND_CFDI
    ):
        """Check the status of a download request."""
        self._ensure_token(token)
        method_name = self._STATUS_METHODS[document_kind]
        response = self._get_sat_method(method_name, document_kind=document_kind)(
            sat_request_id
        )
        return self._normalize_status_response(response)

    def download_package(
        self, token, rfc, package_id, document_kind=DOCUMENT_KIND_CFDI
    ):
        """Download a package from the SAT."""
        self._ensure_token(token)
        method_name = self._DOWNLOAD_METHODS[document_kind]
        response, paquete = self._get_sat_method(
            method_name, document_kind=document_kind
        )(package_id)
        return self._normalize_download_response(response, paquete)

    def validate_cfdi(self, issuer_rfc, receiver_rfc, total, uuid):
        """Validate a CFDI status against the SAT public consulta endpoint."""
        template = (
            '<Envelope xmlns="http://schemas.xmlsoap.org/soap/envelope/" '
            'xmlns:tem="http://tempuri.org/"><Body><tem:Consulta>'
            "<tem:expresionImpresa>"
            f"<![CDATA[?re={issuer_rfc}&rr={receiver_rfc}&tt={total}&id={uuid}]]>"
            "</tem:expresionImpresa></tem:Consulta></Body></Envelope>"
        )
        host = "https://consultaqr.facturaelectronica.sat.gob.mx"
        xml = self._sat._request(
            soap_url=f"{host}/ConsultaCFDIService.svc",
            data=template,
            soap_action="http://tempuri.org/IConsultaCFDIService/Consulta",
            verify=True,
            needs_token_fn=None,
        )
        result_node = xml.find("{*}Body/{*}ConsultaResponse/{*}ConsultaResult")
        result = {QName(item.tag).localname: item.text for item in result_node}
        return {
            "codigo_estatus": result.get("CodigoEstatus", ""),
            "es_cancelable": result.get("EsCancelable", ""),
            "estado": result.get("Estado", ""),
        }

    def _get_sat_method(self, method_name, document_kind=None):
        """Resolve a SAT web-service method, with legacy retention fallback."""
        if hasattr(self._sat, method_name):
            return getattr(self._sat, method_name)
        if (
            document_kind == self.DOCUMENT_KIND_RETENTION
            and method_name
            in (
                "recover_retencion_emitted_request",
                "recover_retencion_received_request",
            )
            and hasattr(self._sat, self._LEGACY_RETENTION_REQUEST)
        ):
            return getattr(self._sat, self._LEGACY_RETENTION_REQUEST)
        raise AttributeError(
            f"'SAT' object has no attribute '{method_name}'. "
            f"Retention downloads require satcfdi >= {self._MIN_SATCFDI_RETENTION}. "
            f"Install or upgrade with: pip install "
            f"'satcfdi>={self._MIN_SATCFDI_RETENTION}'"
        )

    @classmethod
    def _resolve_tipo_solicitud(cls, request_type):
        if request_type == cls.REQUEST_TYPE_METADATA:
            return TipoDescargaMasivaTerceros.METADATA
        return TipoDescargaMasivaTerceros.CFDI

    @staticmethod
    def _ensure_token(token):
        """Keep token parameter for API compatibility; satcfdi manages auth."""
        if not token:
            raise ValueError("SAT token is required.")

    @staticmethod
    def _normalize_request_response(response):
        return {
            "cod_estatus": response.get("CodEstatus", ""),
            "sat_request_id": response.get("IdSolicitud", ""),
            "message": response.get("Mensaje", ""),
        }

    @staticmethod
    def _normalize_status_response(response):
        estado = response.get("EstadoSolicitud", 0)
        if hasattr(estado, "value"):
            estado = estado.value
        paquetes = response.get("IdsPaquetes") or []
        reported_cfdi_count = response.get("NumeroCFDIs", 0)
        return {
            "cod_estatus": response.get("CodEstatus", ""),
            "request_status": estado,
            "request_status_code": response.get("CodigoEstadoSolicitud", ""),
            "reported_cfdi_count": reported_cfdi_count,
            "packages": paquetes,
            "message": response.get("Mensaje", ""),
        }

    @staticmethod
    def _normalize_download_response(response, paquete):
        return {
            "cod_estatus": response.get("CodEstatus", ""),
            "package_b64": paquete or "",
            "message": response.get("Mensaje", ""),
        }
