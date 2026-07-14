# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import csv
import hashlib
import io
import re

# SAT metadata Estado values (case-insensitive normalization).
SAT_STATUS_VALID = "valid"
SAT_STATUS_CANCELLED = "cancelled"
SAT_STATUS_IN_PROGRESS = "in_progress"

_STATUS_MAP = {
    "valid": SAT_STATUS_VALID,
    "vigente": SAT_STATUS_VALID,
    "cancelled": SAT_STATUS_CANCELLED,
    "cancelado": SAT_STATUS_CANCELLED,
    "in progress": SAT_STATUS_IN_PROGRESS,
    "en proceso": SAT_STATUS_IN_PROGRESS,
    "enproceso": SAT_STATUS_IN_PROGRESS,
}


def normalize_sat_status(value):
    """Normalize SAT metadata Estado column to internal selection keys."""
    if not value:
        return False
    key = str(value).strip().lower()
    key = re.sub(r"\s+", " ", key)
    return _STATUS_MAP.get(key, key.replace(" ", "_"))


def build_request_fingerprint(
    company_id,
    document_kind,
    direction,
    request_type,
    date_from,
    date_to,
):
    """Build a stable fingerprint to avoid duplicate SAT requests (code 5002)."""
    payload = "|".join(
        [
            str(company_id),
            document_kind or "",
            direction or "",
            request_type or "",
            date_from.isoformat() if date_from else "",
            date_to.isoformat() if date_to else "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_metadata_content(content_bytes):
    """Parse SAT metadata file content into list of dicts.

    SAT metadata files are typically pipe-delimited text with a header row.
    Column names vary slightly; we map common variants to normalized keys.
    """
    text = content_bytes.decode("utf-8-sig", errors="replace")
    if not text.strip():
        return []

    delimiter = "|" if "|" in text.splitlines()[0] else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows = []
    for raw in reader:
        normalized = {
            _normalize_header(k): (v or "").strip() for k, v in raw.items() if k
        }
        uuid = (
            normalized.get("uuid")
            or normalized.get("folio_fiscal")
            or normalized.get("foliofiscal")
        )
        if not uuid:
            continue
        rows.append(
            {
                "uuid": uuid.upper(),
                "issuer_rfc": normalized.get("issuer_rfc", ""),
                "issuer_name": normalized.get("issuer_name", ""),
                "receiver_rfc": normalized.get("receiver_rfc", ""),
                "receiver_name": normalized.get("receiver_name", ""),
                "issue_date": normalized.get("issue_date", ""),
                "certification_date": normalized.get("certification_date", ""),
                "stamp_date": normalized.get("certification_date", ""),
                "pac_certifico": normalized.get("pac_certifico", ""),
                "total": normalized.get("total", ""),
                "voucher_effect": normalized.get("voucher_effect", ""),
                "voucher_type": normalized.get("voucher_effect", ""),
                "sat_status": normalize_sat_status(
                    normalized.get("estado") or normalized.get("estatus")
                ),
                "cancellation_date": normalized.get("cancellation_date", ""),
            }
        )
    return rows


def _normalize_header(header):
    key = header.strip().lower()
    key = re.sub(r"[^\w\s]", "", key)
    key = re.sub(r"\s+", "_", key)
    aliases = {
        "foliofiscal": "uuid",
        "folio_fiscal": "uuid",
        "rfc_emisor": "issuer_rfc",
        "nombre_emisor": "issuer_name",
        "rfc_receptor": "receiver_rfc",
        "nombre_receptor": "receiver_name",
        "fecha_emision": "issue_date",
        "fecha_certificacion": "certification_date",
        "fecha_cancelacion": "cancellation_date",
        "efecto_comprobante": "voucher_effect",
        "efecto": "voucher_effect",
        "estatus": "estado",
    }
    return aliases.get(key, key)
