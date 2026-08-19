import json
import logging

from satcfdi.cfdi import CFDI
from satcfdi.models import Signer
from satcfdi.pacs import Accept, CancelReason

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services import cfdi_normalize, pac_registry

_logger = logging.getLogger(__name__)

# PAC wrappers that hide the real ModelState / messageDetail payload.
_OPAQUE_PAC_MESSAGES = frozenset(
    {
        "error no clasificado",
        "error no clasificado.",
        "la solicitud no es válida.",
        "la solicitud no es valida.",
        "la solicitud no es válida",
        "la solicitud no es valida",
    }
)


class CFDIService(models.Model):
    _name = "l10n_mx_cfdi.cfdi_service"
    _description = "CFDI Service Settings"

    name = fields.Char(required=True)
    company_ids = fields.Many2many(
        "res.company", string="Companies", default=lambda self: self.env.company
    )
    provider = fields.Selection(
        selection=lambda self: pac_registry.provider_selection(),
        required=True,
        default="finkok",
        groups="base.group_system",
    )
    sandbox_mode = fields.Boolean(default=False, groups="base.group_system")
    stamps_available = fields.Integer(string="Stamps available", readonly=True)

    # Shared / provider-specific credentials
    user = fields.Char(groups="base.group_system")
    password = fields.Char(groups="base.group_system")
    pac_token = fields.Char(string="PAC Token", groups="base.group_system")
    pac_rfc = fields.Char(string="PAC RFC", groups="base.group_system")
    pac_client_id = fields.Char(string="PAC Client ID", groups="base.group_system")
    pac_contrato = fields.Char(string="PAC Contract", groups="base.group_system")
    pac_requestor = fields.Char(string="PAC Requestor", groups="base.group_system")
    pac_country = fields.Char(
        string="PAC Country", default="MX", groups="base.group_system"
    )

    supports_issue = fields.Boolean(compute="_compute_pac_capabilities")
    supports_cancel = fields.Boolean(compute="_compute_pac_capabilities")

    @api.model
    def _format_pac_error(self, exc):
        """Extract a user-readable detail from satcfdi / PAC exceptions.

        satcfdi raises ``ResponseError`` with either a ``requests.Response``
        (SW, opaque ``<Response [400]>``) or a payload dict (Prodigia).
        """
        response = getattr(exc, "response", None)
        if response is not None:
            detail = self._extract_pac_response_detail(response)
            if detail:
                return detail
        text = str(exc).strip()
        return text or repr(exc)

    @api.model
    def _extract_pac_response_detail(self, response):
        if isinstance(response, dict):
            return self._detail_from_pac_mapping(response)

        data = None
        if hasattr(response, "json"):
            try:
                data = response.json()
            except Exception:  # noqa: BLE001 - PAC responses vary widely
                data = None
        if isinstance(data, dict):
            detail = self._detail_from_pac_mapping(data)
            if detail:
                return detail

        text = (getattr(response, "text", None) or "").strip()
        if text:
            return text[:2000]

        status = getattr(response, "status_code", None)
        reason = getattr(response, "reason", None) or ""
        if status:
            return f"HTTP {status} {reason}".strip()
        return None

    @api.model
    def _pac_mapping_text(self, data, keys):
        """Return the first non-empty string for ``keys`` in ``data``."""
        if not isinstance(data, dict):
            return None
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @api.model
    def _combine_pac_messages(self, summary, detail):
        """Merge PAC summary + detail without duplicating the same text."""
        if summary and detail:
            if detail in summary:
                return summary
            if summary in detail:
                return detail
            return f"{summary} {detail}"
        return detail or summary

    @api.model
    def _is_opaque_pac_message(self, combined):
        """True when the PAC text is (or contains) a known opaque wrapper."""
        if not combined:
            return False
        text = combined.strip().lower()
        if text in _OPAQUE_PAC_MESSAGES:
            return True
        # Facturama sometimes prefixes CFDI40999 / extra punctuation.
        return any(opaque in text for opaque in _OPAQUE_PAC_MESSAGES)

    @api.model
    def _with_opaque_pac_dump(self, combined, data):
        """Append JSON dump when the PAC message is an opaque wrapper."""
        if not combined:
            return None
        if not self._is_opaque_pac_message(combined):
            return combined
        dumped = self._dump_pac_payload(data)
        return f"{combined}\n{dumped}" if dumped else combined

    @api.model
    def _detail_from_pac_mapping(self, data):
        """Pull the most useful message out of PAC JSON payloads.

        SW often returns a short wrapper in ``message`` (e.g. "La solicitud no
        es válida.") and the real SAT/CFDI reason in ``messageDetail``. Prefer
        combining both when they differ so operators see the CFDI40 code.
        """
        if not isinstance(data, dict):
            return None

        # Prodigia: {'servicioTimbrado': {'mensaje': '...', 'codigo': 2, ...}}
        servicio = data.get("servicioTimbrado")
        if isinstance(servicio, dict):
            nested = self._detail_from_pac_mapping(servicio)
            if nested:
                return nested

        summary = self._pac_mapping_text(
            data, ("mensaje", "message", "Message", "msg", "error", "Error")
        )
        detail = self._pac_mapping_text(
            data, ("messageDetail", "MessageDetail", "detalle", "description")
        )
        # Facturama (ASP.NET) often returns only "La solicitud no es válida."
        # with the real field errors in ModelState.
        model_state_text = self._format_pac_model_state(
            data.get("ModelState") or data.get("modelState")
        )
        combined = self._combine_pac_messages(summary, detail)
        if combined and model_state_text:
            return f"{combined}\n{model_state_text}"
        if model_state_text:
            return model_state_text
        if combined:
            # Only dump the raw JSON when no messageDetail was extracted: if
            # ``detail`` already carried the useful CFDI40 reason, the combined
            # text is sufficient and dumping would duplicate the payload.
            if detail:
                return combined
            return self._with_opaque_pac_dump(combined, data)

        for key in ("mensaje", "message", "Message", "error", "Error"):
            value = data.get(key)
            if isinstance(value, dict):
                nested = self._detail_from_pac_mapping(value)
                if nested:
                    return nested

        # SW sometimes nests under data
        nested_data = data.get("data")
        if isinstance(nested_data, dict):
            nested = self._detail_from_pac_mapping(nested_data)
            if nested:
                return nested
        if isinstance(nested_data, str) and nested_data.strip():
            return nested_data.strip()

        # Do not dump arbitrary leftover JSON (e.g. {"codigo": 1}). Opaque
        # wrappers like Facturama "Error no clasificado" already append a dump
        # via _with_opaque_pac_dump when a known opaque message is present.
        return None

    @api.model
    def _dump_pac_payload(self, data):
        """Serialize opaque PAC JSON for operator-facing errors (truncated)."""
        if not isinstance(data, dict) or not data:
            return None
        try:
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)[:2000]
        except (TypeError, ValueError):
            return str(data)[:2000]

    @api.model
    def _format_pac_model_state(self, model_state):
        """Format Facturama/ASP.NET ModelState into a readable string."""
        if not isinstance(model_state, dict) or not model_state:
            return None
        try:
            return json.dumps(model_state, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(model_state)

    @api.depends("provider")
    def _compute_pac_capabilities(self):
        for service in self:
            if not service.provider:
                service.supports_issue = False
                service.supports_cancel = False
                continue
            provider = pac_registry.get_provider(service.provider)
            service.supports_issue = provider.supports_issue
            service.supports_cancel = provider.supports_cancel

    def _get_pac(self):
        self.ensure_one()
        if not self.provider:
            raise UserError(self.env._("PAC provider is not configured."))
        try:
            return pac_registry.build_pac(self)
        except Exception as exc:
            _logger.exception("Failed to initialize PAC client")
            raise UserError(
                self.env._("Cannot initialize the PAC client: %s", str(exc))
            ) from exc

    def _get_csd_signer(self, issuer):
        """Build a satcfdi Signer from the issuer CSD."""
        cert = cfdi_normalize.decode_binary_field(issuer.certificate_file)
        key = cfdi_normalize.decode_binary_field(issuer.key_file)
        if not cert or not key or not issuer.key_password:
            raise UserError(self.env._("Digital certificate not configured."))
        try:
            signer = Signer.load(
                certificate=cert,
                key=key,
                password=issuer.key_password,
            )
        except Exception as exc:
            raise UserError(
                self.env._("Invalid digital certificate: %s", str(exc))
            ) from exc
        if issuer.vat and signer.rfc and signer.rfc.upper() != issuer.vat.upper():
            raise UserError(
                self.env._(
                    "CSD RFC %(csd_rfc)s does not match issuer RFC %(issuer_rfc)s.",
                    csd_rfc=signer.rfc,
                    issuer_rfc=issuer.vat,
                )
            )
        return signer

    def _get_cancel_signer(self, issuer):
        """Prefer company FIEL (l10n_mx_sat) then fall back to issuer CSD."""
        company = issuer.company_id or self.env.company
        if (
            hasattr(company, "l10n_mx_sat_fiel_cer")
            and company.l10n_mx_sat_fiel_cer
            and company.l10n_mx_sat_fiel_key
            and company.l10n_mx_sat_fiel_password
        ):
            try:
                return Signer.load(
                    certificate=cfdi_normalize.decode_binary_field(
                        company.l10n_mx_sat_fiel_cer
                    ),
                    key=cfdi_normalize.decode_binary_field(
                        company.l10n_mx_sat_fiel_key
                    ),
                    password=company.l10n_mx_sat_fiel_password,
                )
            except Exception:
                _logger.warning("Company FIEL could not be loaded; falling back to CSD")
        return self._get_csd_signer(issuer)

    def validate_csd(self, issuer):
        """Validate that the issuer CSD can be loaded (local registration)."""
        self.ensure_one()
        return self._get_csd_signer(issuer)

    def upload_issuer_csd(self, issuer):
        """Upload issuer CSD to PACs that require remote registration (Facturama)."""
        self.ensure_one()
        provider = pac_registry.get_provider(self.provider)
        if provider.code != "facturama":
            return None
        signer = self._get_csd_signer(issuer)
        pac = self._get_pac()
        cert = cfdi_normalize.decode_binary_field(issuer.certificate_file)
        key = cfdi_normalize.decode_binary_field(issuer.key_file)
        try:
            return pac.upload_csd(
                rfc=issuer.vat or signer.rfc,
                certificate=cert,
                key=key,
                password=issuer.key_password,
            )
        except Exception as exc:
            _logger.exception("Facturama CSD upload failed")
            raise UserError(
                self.env._(
                    "Cannot upload the CSD to Facturama: %s",
                    self._format_pac_error(exc),
                )
            ) from exc

    def delete_issuer_csd(self, issuer):
        """Remove issuer CSD from PACs that store it remotely (Facturama)."""
        self.ensure_one()
        provider = pac_registry.get_provider(self.provider)
        if provider.code != "facturama" or not issuer.vat:
            return
        pac = self._get_pac()
        try:
            pac.delete_csd(issuer.vat)
        except Exception as exc:
            _logger.warning(
                "Facturama CSD delete failed for %s: %s",
                issuer.vat,
                self._format_pac_error(exc),
            )

    def create_cfdi(self, cfdi, issuer=None):
        """Seal/stamp a CFDI via the configured PAC and return a normalized result.

        Prefers ``pac.issue()`` when the provider supports it; otherwise signs
        locally with the issuer CSD and calls ``pac.stamp()``.
        """
        self.ensure_one()
        if issuer is None:
            raise UserError(self.env._("Issuer is required to stamp a CFDI."))

        pac = self._get_pac()
        provider = pac_registry.get_provider(self.provider)
        if provider.code == "facturama":
            from ..services import facturama_adapter

            pac = facturama_adapter.ensure_facturama_pac_for_cfdi(pac, self, cfdi)
        # Prefer XML+PDF when the PAC can return both in one call (avoids brittle
        # recover() shapes such as SW Sapien's raw dict response).
        accept = Accept.XML_PDF
        try:
            if provider.supports_issue:
                document = pac.issue(cfdi, accept=accept)
            else:
                signer = self._get_csd_signer(issuer)
                if hasattr(cfdi, "sign"):
                    cfdi.sign(signer)
                    cfdi = cfdi.process() if hasattr(cfdi, "process") else cfdi
                elif isinstance(cfdi, CFDI) and not cfdi.get("Sello"):
                    cfdi.sign(signer)
                document = pac.stamp(cfdi, accept=accept)
        except UserError:
            raise
        except NotImplementedError as exc:
            detail = str(exc)
            if provider.code == "facturama" and (
                "Complemento" in detail
                or "CartaPorte" in detail
                or "Comercio Exterior" in detail
                or "ForeignTrade" in detail
            ):
                raise UserError(
                    self.env._(
                        "Facturama could not map this CFDI complement "
                        "(Carta Porte 3.1 and Comercio Exterior via FacturamaWeb "
                        "are supported; other complements may not be). Details: %s",
                        detail,
                    )
                ) from exc
            raise UserError(
                self.env._(
                    "The selected PAC does not support this operation: %s", detail
                )
            ) from exc
        except Exception as exc:
            _logger.exception("PAC stamping failed")
            raise UserError(
                self.env._(
                    "Error when creating the CFDI: %s",
                    self._format_pac_error(exc),
                )
            ) from exc

        result = cfdi_normalize.normalize_pac_document(document)
        _logger.info("CFDI stamped: %s", result.get("uuid"))
        return result

    @api.model
    def _pac_recover_file(self, document, kind: str):
        """Extract PDF/XML bytes from a satcfdi ``Document`` or raw PAC dict.

        Some adapters (SW Sapien ``recover``) return the HTTP JSON payload
        instead of a ``Document`` instance.
        """
        if document is None:
            return None
        value = getattr(document, kind, None)
        if value:
            return value
        if not isinstance(document, dict):
            return None

        candidates = [
            document.get(kind),
            document.get(kind.upper()),
            document.get(kind.capitalize()),
        ]
        data = document.get("data")
        if isinstance(data, dict):
            candidates.extend(
                [
                    data.get(kind),
                    data.get(kind.upper()),
                    data.get("contentB64"),
                    data.get("content"),
                    data.get("Content"),
                ]
            )
        candidates.extend(
            [
                document.get("contentB64"),
                document.get("content"),
                document.get("Content"),
            ]
        )
        for candidate in candidates:
            if not candidate:
                continue
            if isinstance(candidate, (bytes, bytearray)):
                return bytes(candidate)
            if isinstance(candidate, str):
                import base64

                try:
                    return base64.b64decode(candidate)
                except Exception:  # noqa: BLE001
                    return candidate.encode("utf-8") if kind == "xml" else None
        return None

    def get_cfdi_pdf(self, tracking_id: str):
        """Try to recover PDF from the PAC when available."""
        self.ensure_one()
        pac = self._get_pac()
        try:
            document = pac.recover(tracking_id, accept=Accept.PDF)
        except NotImplementedError as exc:
            raise UserError(
                self.env._("The selected PAC does not provide PDF recovery.")
            ) from exc
        except Exception as exc:
            raise UserError(
                self.env._(
                    "Cannot recover CFDI PDF: %s",
                    self._format_pac_error(exc),
                )
            ) from exc
        pdf = self._pac_recover_file(document, "pdf")
        if not pdf:
            raise UserError(self.env._("PAC did not return a PDF document."))
        return {"Content": base64_encode_pdf(pdf)}

    def get_cfdi_xml(self, tracking_id: str):
        self.ensure_one()
        pac = self._get_pac()
        try:
            document = pac.recover(tracking_id, accept=Accept.XML)
        except NotImplementedError as exc:
            raise UserError(
                self.env._("The selected PAC does not provide XML recovery.")
            ) from exc
        except Exception as exc:
            raise UserError(
                self.env._(
                    "Cannot recover CFDI XML: %s",
                    self._format_pac_error(exc),
                )
            ) from exc
        xml = self._pac_recover_file(document, "xml") or b""
        return {"Content": xml}

    def cancel_cfdi(
        self, cfdi_or_xml, reason, uuid_replacement=None, issuer=None, document_id=None
    ):
        self.ensure_one()
        provider = pac_registry.get_provider(self.provider)
        if not provider.supports_cancel:
            raise UserError(
                self.env._(
                    "The selected PAC (%s) does not support cancellation.",
                    provider.label,
                )
            )

        pac = self._get_pac()
        cfdi = self._as_cfdi(cfdi_or_xml)
        cancel_reason = self._map_cancel_reason(reason)
        signer = None
        if provider.requires_signer_for_cancel:
            if issuer is None:
                raise UserError(
                    self.env._("Issuer is required to cancel with this PAC.")
                )
            signer = self._get_cancel_signer(issuer)

        substitution_id = None
        if uuid_replacement:
            substitution_id = (
                uuid_replacement.uuid
                if hasattr(uuid_replacement, "uuid")
                else str(uuid_replacement)
            )

        cancel_kwargs = {
            "reason": cancel_reason,
            "substitution_id": substitution_id,
            "signer": signer,
        }
        # Facturama Multiemisor cancels by document Id (stored as tracking_id)
        if document_id and provider.code == "facturama":
            cancel_kwargs["document_id"] = document_id

        try:
            ack = pac.cancel(cfdi, **cancel_kwargs)
        except Exception as exc:
            _logger.exception("PAC cancel failed")
            raise UserError(
                self.env._(
                    "Error when cancelling the CFDI: %s",
                    self._format_pac_error(exc),
                )
            ) from exc

        code = getattr(ack, "code", None)
        status_code, message = self._split_cancel_ack(code)
        status = self._map_cancel_status(status_code)
        return {
            "Status": status,
            "Message": message or (str(status_code) if status_code is not None else ""),
            "Acuse": getattr(ack, "acuse", None),
        }

    def get_cancellation_request_proof(self, tracking_id: str):
        """Return cancellation acknowledgment PDF/XML when available via recover."""
        self.ensure_one()
        # satcfdi does not provide a unified "acuse PDF" API; return empty for now
        # when no stored acuse is available on the document.
        raise UserError(
            self.env._(
                "Cancellation request proof must be retrieved from the stored "
                "acknowledgment on the document."
            )
        )

    def check_cfdi_status(self, uuid, issuer_rfc, receiver_rfc, amount_total):
        """Query CFDI status through the PAC when supported; otherwise unknown."""
        self.ensure_one()
        pac = self._get_pac()
        try:
            # Build a minimal CFDI-like mapping for adapters that implement status()
            stub = CFDI(
                {
                    "Complemento": {"TimbreFiscalDigital": {"UUID": uuid}},
                    "Emisor": {"Rfc": issuer_rfc},
                    "Receptor": {"Rfc": receiver_rfc},
                    "Total": amount_total,
                }
            )
            res = pac.status(stub)
        except NotImplementedError:
            return "unknown"
        except Exception:
            _logger.exception("PAC status check failed")
            return "unknown"

        status = None
        if isinstance(res, dict):
            status = res.get("Status") or res.get("estado") or res.get("Estado")
        status = str(status or "")
        if status in ("Vigente", "published", "Active"):
            return "published"
        if status in ("Cancelado", "cancelled", "canceled", "Cancelled"):
            return "canceled"
        if status in ("No Encontrado", "unknown"):
            return "unknown"
        return "unknown"

    @api.model
    def _map_cancel_reason(self, reason):
        mapping = {
            "01": CancelReason.COMPROBANTE_EMITIDO_CON_ERRORES_CON_RELACION,
            "02": CancelReason.COMPROBANTE_EMITIDO_CON_ERRORES_SIN_RELACION,
            "03": CancelReason.NO_SE_LLEVO_A_CABO_LA_OPERACION,
            "04": CancelReason.OPERACION_NORMATIVA_RELACIONADA_EN_LA_FACTURA_GLOBAL,
        }
        if isinstance(reason, CancelReason):
            return reason
        code = str(reason or "02")
        if code not in mapping:
            raise UserError(self.env._("Invalid cancellation reason: %s", code))
        return mapping[code]

    @api.model
    def _split_cancel_ack(self, code):
        """Return ``(status_code, message)`` from a PAC cancel acknowledgment.

        Facturama (via our adapter) may pass
        ``{"Status": "canceled", "Message": "Cancelado sin Aceptacion"}``.
        Other PACs usually return a plain status/code string.
        """
        if isinstance(code, dict):
            status = code.get("Status") or code.get("status") or code.get("code")
            message = code.get("Message") or code.get("message") or ""
            if isinstance(message, str):
                message = message.strip()
            else:
                message = str(message) if message else ""
            return status, message
        if code is None:
            return None, ""
        return code, str(code)

    @api.model
    def _map_cancel_status(self, code):
        """Best-effort map PAC cancel acknowledgment codes to document states."""
        if isinstance(code, dict):
            code, _message = self._split_cancel_ack(code)
        if code is None:
            return "canceled"
        text = str(code).lower()
        if any(token in text for token in ("pend", "201", "202")):
            return "pending"
        if any(token in text for token in ("reject", "deneg", "205")):
            return "rejected"
        # Facturama: CFDI still active (related documents block cancel)
        if text in ("active", "activa", "vigente"):
            return "active"
        return "canceled"

    @api.model
    def _as_cfdi(self, cfdi_or_xml):
        if isinstance(cfdi_or_xml, CFDI):
            return cfdi_or_xml
        xml_bytes = None
        if isinstance(cfdi_or_xml, (bytes, bytearray)):
            xml_bytes = bytes(cfdi_or_xml)
        elif isinstance(cfdi_or_xml, str):
            xml_bytes = cfdi_or_xml.encode("utf-8")
        if xml_bytes is None:
            raise UserError(self.env._("Invalid CFDI payload for cancellation."))
        try:
            return CFDI.from_string(xml_bytes)
        except Exception:
            # Incomplete XML (common in tests / legacy) still carries UUID.
            from lxml import etree

            try:
                root = etree.fromstring(xml_bytes)
            except etree.XMLSyntaxError as err:
                raise UserError(
                    self.env._(
                        "Cannot cancel CFDI: stamped XML is invalid or missing UUID."
                    )
                ) from err
            timbre = root.find(
                ".//{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital"
            )
            uuid = timbre.get("UUID") if timbre is not None else None
            if not uuid:
                raise UserError(
                    self.env._(
                        "Cannot cancel CFDI: stamped XML is invalid or missing UUID."
                    )
                ) from None
            return CFDI({"Complemento": {"TimbreFiscalDigital": {"UUID": uuid}}})


def base64_encode_pdf(pdf_bytes: bytes) -> str:
    import base64

    return base64.b64encode(pdf_bytes).decode("ascii")
