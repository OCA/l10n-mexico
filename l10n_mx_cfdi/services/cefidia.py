"""Cefidia PAC client with the satcfdi ``PAC`` interface used by cfdi.service.

satcfdi ships no Cefidia adapter, so this module talks to the Cefidia JSON
API (https://docs.cefidia.com/referencia/api/) directly:

- ``stamp()``  -> ``POST /v1/signed-documents`` with the CFDI already sealed
  locally with the issuer CSD. Cefidia forwards it to the PAC untouched, so
  every complement (Carta Porte, Comercio Exterior, Pagos...) is supported.
- ``recover()`` -> ``GET /v1/documents/{id}`` then download the signed links.
- ``cancel()`` -> ``POST /v1/documents/{uuid}/cancel``. Requires the CSD to be
  uploaded on the Cefidia web page of the taxpayer; it returns no acuse.
- ``status()`` -> ``GET /v1/documents/{uuid}``.

Authentication is a bearer token (``cfd_...``). There is no separate sandbox
host: the environment is decided by the certificate in the XML (SAT test
taxpayers are added with ``POST /v1/test-taxpayers``).

Errors are RFC 9457 ``application/problem+json``; they are raised as satcfdi
``ResponseError`` so ``cfdi.service._format_pac_error`` can render them.
"""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

import requests
from satcfdi.cfdi import CFDI
from satcfdi.exceptions import ResponseError
from satcfdi.pacs import Accept, CancelationAcknowledgment, Document, Environment

_logger = logging.getLogger(__name__)

BASE_URL = "https://cefidia.com"
DEFAULT_TIMEOUT = 60
# ``stamping`` means the PAC is still processing: poll the document briefly.
POLL_ATTEMPTS = 5
POLL_INTERVAL = 2


class CefidiaRejection(ResponseError):
    """The PAC/SAT rejected the CFDI (HTTP 200 with a ``rejection`` body)."""

    def __init__(self, rejection: dict):
        rejection = rejection or {}
        code = rejection.get("code") or ""
        message = rejection.get("message") or ""
        path = rejection.get("path")
        problem = {
            "code": code,
            "detail": f"{code}: {message}".strip(": ") or "CFDI rejected by the PAC",
        }
        if path:
            problem["fields"] = [{"path": path, "message": message}]
        super().__init__(problem)


class Cefidia:
    """Minimal Cefidia client exposing the satcfdi PAC methods we rely on."""

    def __init__(
        self,
        token: str,
        environment: Environment | None = None,
        base_url: str = BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        if not token:
            raise ValueError("Cefidia requires an API token (cfd_...).")
        self.token = token
        # Kept for interface parity only: Cefidia picks the environment from
        # the certificate in the XML, not from the host or a flag.
        self.environment = environment
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    # ------------------------------------------------------------------ HTTP

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json, application/problem+json",
        }

    def _request(self, method: str, path: str, json=None, params=None) -> dict:
        response = self.session.request(
            method,
            f"{self.base_url}/{path.lstrip('/')}",
            json=json,
            params={k: v for k, v in (params or {}).items() if v},
            headers=self._headers(),
            timeout=self.timeout,
        )
        if not response.ok:
            raise ResponseError(response)
        if not response.content:
            return {}
        return response.json()

    def _download(self, url: str) -> bytes:
        """Fetch a signed XML/PDF link; send the token only to the API host."""
        headers = {}
        if urlparse(url).netloc == urlparse(self.base_url).netloc:
            headers = self._headers()
        response = self.session.get(url, headers=headers, timeout=self.timeout)
        if not response.ok:
            raise ResponseError(response)
        return response.content

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _xml_text(cfdi) -> str:
        if isinstance(cfdi, (bytes, bytearray)):
            return bytes(cfdi).decode("utf-8")
        if isinstance(cfdi, str):
            return cfdi
        return cfdi.xml_bytes().decode("utf-8")

    @staticmethod
    def _uuid(cfdi) -> str | None:
        try:
            return cfdi["Complemento"]["TimbreFiscalDigital"]["UUID"]
        except (KeyError, TypeError):
            return None

    @staticmethod
    def _issuer_rfc(cfdi) -> str | None:
        try:
            return cfdi["Emisor"]["Rfc"]
        except (KeyError, TypeError):
            return None

    def get_document(self, reference: str, taxpayer: str | None = None) -> dict:
        return self._request(
            "get", f"v1/documents/{reference}", params={"taxpayer": taxpayer}
        )

    def _wait_stamped(self, doc: dict, taxpayer: str | None = None) -> dict:
        attempts = 0
        while doc.get("state") == "stamping" and attempts < POLL_ATTEMPTS:
            attempts += 1
            time.sleep(POLL_INTERVAL)
            doc = self.get_document(doc["id"], taxpayer=taxpayer)
        if doc.get("state") == "stamping":
            raise ResponseError(
                {
                    "code": "stamping",
                    "detail": (
                        f"Cefidia is still stamping document {doc.get('id')}. "
                        "Retry in a few minutes; sending the same sealed XML "
                        "again returns the same document."
                    ),
                }
            )
        if doc.get("rejection") and not doc.get("uuid"):
            raise CefidiaRejection(doc["rejection"])
        return doc

    def _to_document(self, doc: dict, accept: Accept) -> Document:
        links = doc.get("links") or {}
        if accept and not links:
            raise ResponseError(
                {
                    "code": "no_links",
                    "detail": (
                        f"Cefidia document {doc.get('id')} has no XML/PDF yet "
                        f"(state: {doc.get('state')})."
                    ),
                }
            )
        xml = self._download(links["xml"]) if accept & Accept.XML else None
        pdf = self._download(links["pdf"]) if accept & Accept.PDF else None
        return Document(document_id=doc["id"], xml=xml, pdf=pdf)

    # ------------------------------------------------------ satcfdi PAC API

    def stamp(self, cfdi: CFDI, accept: Accept = Accept.XML) -> Document:
        """Stamp a CFDI 4.0 already sealed with the issuer CSD."""
        res = self._request(
            "post", "v1/signed-documents", json={"xml": self._xml_text(cfdi)}
        )
        if "rejection" in res and not res.get("id"):
            raise CefidiaRejection(res["rejection"])
        doc = self._wait_stamped(res, taxpayer=self._issuer_rfc(cfdi))
        return self._to_document(doc, accept)

    def issue(self, cfdi: CFDI, accept: Accept = Accept.XML) -> Document:
        raise NotImplementedError(
            "Cefidia stamps locally sealed XML; use stamp() with the issuer CSD."
        )

    def recover(self, document_id: str, accept: Accept = Accept.XML) -> Document:
        doc = self.get_document(document_id)
        return self._to_document(doc, accept)

    def cancel(
        self,
        cfdi: CFDI,
        reason,
        substitution_id: str | None = None,
        signer=None,
        document_id: str | None = None,
    ) -> CancelationAcknowledgment:
        """Cancel through Cefidia (uses the CSD stored on Cefidia, not ``signer``)."""
        del signer
        reference = self._uuid(cfdi) or document_id
        if not reference:
            raise ValueError("Cannot cancel: CFDI has no UUID and no document id.")
        motivo = getattr(reason, "value", reason)
        payload = {"motivo": str(motivo), "taxpayer": self._issuer_rfc(cfdi)}
        if substitution_id and str(motivo) == "01":
            payload["replacement"] = substitution_id
        payload = {k: v for k, v in payload.items() if v}
        res = self._request("post", f"v1/documents/{reference}/cancel", json=payload)
        state = res.get("state")
        status = {
            "canceled": "canceled",
            "waiting_acceptance": "pending",
        }.get(state, state)
        message = res.get("message") or (res.get("document") or {}).get("message")
        if not message and state == "waiting_acceptance":
            message = (
                "Cancellation requested; waiting for the receiver to accept it. "
                "Cefidia checks the SAT and notifies by email."
            )
        return CancelationAcknowledgment(
            code={"Status": status, "Message": message or ""}, acuse=None
        )

    def status(self, cfdi: CFDI) -> dict:
        """Return ``{"Status": "Vigente" | "Cancelado" | "No Encontrado"}``."""
        uuid = self._uuid(cfdi)
        try:
            doc = self.get_document(uuid, taxpayer=self._issuer_rfc(cfdi))
        except ResponseError as exc:
            response = getattr(exc, "response", None)
            if getattr(response, "status_code", None) == 404:
                return {"Status": "No Encontrado"}
            raise
        state = (doc.get("state") or "").lower()
        sat_state = (doc.get("sat_state") or "").lower()
        if state == "canceled" or "cancelad" in sat_state:
            label = "Cancelado"
        elif state in ("stamped", "cancel_pending") or "vigente" in sat_state:
            label = "Vigente"
        else:
            label = "No Encontrado"
        return {
            "Status": label,
            "state": doc.get("state"),
            "sat_state": doc.get("sat_state"),
        }
