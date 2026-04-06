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
    """Adaptador para los servicios web del SAT via cfdiclient.

    Clase Python pura, sin dependencia del ORM de Odoo.
    Intercambiable via factory res.company.l10n_mx_sat_get_client().
    """

    def __init__(self, cer_der, key_der, password):
        """Inicializa el cliente con credenciales FIEL.

        :param cer_der: certificado en formato DER (bytes)
        :param key_der: llave privada en formato DER (bytes)
        :param password: contrasena de la llave privada (str)
        """
        self._fiel = Fiel(cer_der, key_der, password)

    def authenticate(self):
        """Autentica con el SAT y retorna el token.

        :raises ValueError: si el token esta vacio
        :return: token de autenticacion SAT
        :rtype: str
        """
        auth = Autenticacion(self._fiel)
        token = auth.obtener_token()
        if not token:
            raise ValueError("El SAT retorno un token vacio.")
        return token

    def request_download(self, token, rfc, fecha_inicial, fecha_final, **kwargs):
        """Envia solicitud de descarga al SAT (Descarga Masiva).

        Fuerza estado_comprobante='Vigente' por defecto porque cfdiclient
        lo deja en None, lo que genera XML mal formado en el SAT.

        :return: dict con claves cod_estatus, id_solicitud, mensaje
        """
        kwargs.setdefault("estado_comprobante", "Vigente")
        solicitud = SolicitaDescargaRecibidos(self._fiel)
        return solicitud.solicitar_descarga(
            token, rfc, fecha_inicial, fecha_final, **kwargs
        )

    def verify_download(self, token, rfc, id_solicitud):
        """Verifica el estado de una solicitud de descarga.

        :return: dict con claves estado_solicitud, paquetes, numero_cfdis, mensaje
        """
        verificacion = VerificaSolicitudDescarga(self._fiel)
        return verificacion.verificar_descarga(token, rfc, id_solicitud)

    def download_package(self, token, rfc, id_paquete):
        """Descarga un paquete del SAT.

        :return: dict con claves cod_estatus, paquete_b64, mensaje
        """
        descarga = DescargaMasiva(self._fiel)
        return descarga.descargar_paquete(token, rfc, id_paquete)

    def validate_cfdi(self, rfc_emisor, rfc_receptor, total, uuid):
        """Valida el estado de un CFDI ante el SAT.

        :return: dict con claves codigo_estatus, es_cancelable, estado
        """
        validacion = Validacion()
        return validacion.obtener_estado(rfc_emisor, rfc_receptor, total, uuid)
