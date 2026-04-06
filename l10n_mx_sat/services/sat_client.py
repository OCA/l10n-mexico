# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging

from cfdiclient import (
    Autenticacion,
    DescargaMasiva,
    Fiel,
    SolicitaDescargaRecibidos,
    Validacion,
    VerificaSolicitudDescarga,
)

_logger = logging.getLogger(__name__)


class SatClient:
    """SAT web service adapter via cfdiclient.

    Pure Python class with no Odoo ORM dependency.
    Swappable through the res.company.l10n_mx_sat_get_client() factory.
    """

    def __init__(self, cer_der, key_der, password):
        """Initialize the client with FIEL credentials.

        :param cer_der: certificate in DER format (bytes)
        :param key_der: private key in DER format (bytes)
        :param password: private key password (str)
        """
        self._fiel = Fiel(cer_der, key_der, password)

    def authenticate(self):
        """Authenticate with the SAT and return the token.

        :raises ValueError: if the token is empty
        :return: SAT authentication token
        :rtype: str
        """
        auth = Autenticacion(self._fiel)
        token = auth.obtener_token()
        if not token:
            raise ValueError("SAT returned an empty token.")
        return token

    def request_download(self, token, rfc, fecha_inicial, fecha_final, **kwargs):
        """Send a download request to the SAT (Descarga Masiva).

        Defaults estado_comprobante to 'Vigente' because cfdiclient leaves
        it as None, which produces malformed XML on the SAT side.

        :return: dict with keys cod_estatus, id_solicitud, mensaje
        """
        kwargs.setdefault("estado_comprobante", "Vigente")
        solicitud = SolicitaDescargaRecibidos(self._fiel)
        return solicitud.solicitar_descarga(
            token, rfc, fecha_inicial, fecha_final, **kwargs
        )

    def verify_download(self, token, rfc, id_solicitud):
        """Check the status of a download request.

        :return: dict with keys estado_solicitud, paquetes, numero_cfdis, mensaje
        """
        verificacion = VerificaSolicitudDescarga(self._fiel)
        return verificacion.verificar_descarga(token, rfc, id_solicitud)

    def download_package(self, token, rfc, id_paquete):
        """Download a package from the SAT.

        :return: dict with keys cod_estatus, paquete_b64, mensaje
        """
        descarga = DescargaMasiva(self._fiel)
        return descarga.descargar_paquete(token, rfc, id_paquete)

    def validate_cfdi(self, rfc_emisor, rfc_receptor, total, uuid):
        """Validate a CFDI status against the SAT.

        :return: dict with keys codigo_estatus, es_cancelable, estado
        """
        validacion = Validacion()
        return validacion.obtener_estado(rfc_emisor, rfc_receptor, total, uuid)
