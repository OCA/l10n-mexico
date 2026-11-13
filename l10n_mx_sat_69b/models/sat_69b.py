# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import csv
import logging
import time

import requests

_logger = logging.getLogger(__name__)

LIST_URL = "http://omawww.sat.gob.mx/cifras_sat/Documents/Listado_Completo_69-B.csv"
CACHE_TTL = 15 * 24 * 60 * 60
GENERIC_RFCS = frozenset({"XAXX010101000", "XEXX010101000"})
BLOCKED_STATUSES = frozenset({"Presunto", "Definitivo"})
# Oficio columns on the public 69-B CSV, SAT publication first, DOF as fallback.
REFERENCE_COLUMNS = {
    "Presunto": (4, 6),
    "Desvirtuado": (8, 10),
    "Definitivo": (12, 14),
    "Sentencia Favorable": (16, 18),
}

_cache = {"fetched_at": 0.0, "by_rfc": None}


class SatListError(Exception):
    """The SAT article 69-B list could not be loaded."""


def clear_cache():
    """Drop the in-memory copy of the SAT list."""
    _cache["fetched_at"] = 0.0
    _cache["by_rfc"] = None


def normalize_rfc(rfc):
    """Return an RFC comparable with the SAT list."""
    return (rfc or "").replace(" ", "").replace("-", "").upper()


def _reference_from_row(row, status):
    for index in REFERENCE_COLUMNS.get(status, ()):
        if index < len(row) and row[index].strip():
            return row[index].strip()
    return ""


def parse_list_69b(text):
    """Parse the SAT 69-B CSV into ``{rfc: {name, status, reference}}``.

    :raises SatListError: when the file has no RFC header.
    """
    header_found = False
    taxpayers = {}
    for row in csv.reader(text.splitlines()):
        if not row:
            continue
        if not header_found:
            if len(row) > 1 and row[1].strip() == "RFC":
                header_found = True
            continue
        if len(row) < 4 or not row[1].strip():
            continue
        rfc = normalize_rfc(row[1])
        status = row[3].strip()
        taxpayers[rfc] = {
            "name": row[2].strip(),
            "status": status,
            "reference": _reference_from_row(row, status),
        }
    if not header_found:
        raise SatListError("SAT list 69-B has no RFC header")
    return taxpayers


def _default_get(url, headers=None, timeout=None):
    return requests.get(url, headers=headers, timeout=timeout)


def load_list(get=None):
    """Return the cached SAT 69-B index, refreshing it when it is stale.

    :param get: optional callable with the same contract as ``requests.get``.
    :raises SatListError: when the list cannot be downloaded and no cache exists.
    """
    now = time.time()
    cached = _cache["by_rfc"]
    if cached is not None and now - _cache["fetched_at"] < CACHE_TTL:
        return cached
    getter = get or _default_get
    try:
        response = getter(
            LIST_URL,
            headers={"User-Agent": "Odoo l10n_mx_sat_69b"},
            timeout=60,
        )
        response.raise_for_status()
        parsed = parse_list_69b(response.content.decode("cp1252"))
    except (requests.RequestException, SatListError, UnicodeError) as error:
        if cached is not None:
            _logger.info("Using cached SAT list 69-B after refresh failure: %s", error)
            return cached
        if isinstance(error, SatListError):
            raise
        raise SatListError("Unable to download SAT list 69-B") from error
    _cache["by_rfc"] = parsed
    _cache["fetched_at"] = now
    return parsed


def lookup_taxpayer(rfc, get=None):
    """Return the 69-B row for ``rfc``, or ``None`` when it is not listed.

    Generic invoice RFCs are ignored. A download failure raises
    :class:`SatListError`.
    """
    rfc = normalize_rfc(rfc)
    if not rfc or rfc in GENERIC_RFCS:
        return None
    return load_list(get=get).get(rfc)
