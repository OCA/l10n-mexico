# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import csv
import io
import time
from unittest.mock import patch

import requests

from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_mx_sat_69b.models import sat_69b


def _csv_text(rows):
    """Build a small 69-B file. Column 1 of the header must be RFC."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["updated"])
    writer.writerow(["title"])
    header = [""] * 20
    header[0] = "No"
    header[1] = "RFC"
    writer.writerow(header)
    writer.writerow([])
    for row in rows:
        padded = list(row) + [""] * (20 - len(row))
        writer.writerow(padded[:20])
    writer.writerow(["short", "row"])
    return buffer.getvalue()


SAMPLE_ROWS = [
    [
        "1",
        "AAA010101AAA",
        "ACME, S.A.",
        "Definitivo",
        "500-05-2020-1",
        "01/01/2020",
        "500-05-2020-1",
        "02/01/2020",
        "",
        "",
        "",
        "",
        "500-05-2024-9",
        "02/02/2024",
    ],
    [
        "2",
        "BBB010101BBB",
        "BETA",
        "Presunto",
        "500-05-2025-2",
        "03/03/2025",
    ],
    [
        "3",
        "CCC010101CCC",
        "GAMMA",
        "Desvirtuado",
        "500-05-2021-3",
        "04/04/2021",
        "",
        "",
        "500-05-2022-4",
    ],
    [
        "4",
        "DDD010101DDD",
        "DELTA",
        "Sentencia Favorable",
        "500-05-2019-5",
        "06/06/2019",
        "",
        "",
        "",
        "",
        "",
        "",
        "500-05-2020-6",
        "",
        "",
        "",
        "500-05-2023-7",
    ],
    ["5", "EEE010101EEE", "EPSILON", "Definitivo", "presuncion only"],
    ["6", "FFF010101FFF", "ZETA", "Otro", "x"],
    ["", " ", "blank rfc", "Definitivo"],
]
CSV = _csv_text(SAMPLE_ROWS)


class _Response:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


@tagged("post_install", "-at_install")
class TestSat69BList(TransactionCase):
    def setUp(self):
        super().setUp()
        sat_69b.clear_cache()

    def test_normalize_rfc(self):
        self.assertEqual(sat_69b.normalize_rfc(" aaa-010101-aaa "), "AAA010101AAA")
        self.assertEqual(sat_69b.normalize_rfc(None), "")
        self.assertEqual(sat_69b.normalize_rfc(False), "")

    def test_parse_statuses_and_references(self):
        parsed = sat_69b.parse_list_69b(CSV)
        self.assertEqual(parsed["AAA010101AAA"]["reference"], "500-05-2024-9")
        self.assertEqual(parsed["AAA010101AAA"]["name"], "ACME, S.A.")
        self.assertEqual(parsed["BBB010101BBB"]["reference"], "500-05-2025-2")
        self.assertEqual(parsed["CCC010101CCC"]["reference"], "500-05-2022-4")
        self.assertEqual(parsed["DDD010101DDD"]["reference"], "500-05-2023-7")
        self.assertEqual(parsed["EEE010101EEE"]["reference"], "")
        self.assertEqual(parsed["FFF010101FFF"]["status"], "Otro")
        self.assertNotIn("", parsed)

    def test_parse_uses_dof_reference_when_sat_oficio_is_empty(self):
        presunto = [
            "2",
            "BBB010101BBB",
            "BETA",
            "Presunto",
            "",
            "03/03/2025",
            "500-05-DOF",
        ]
        rows = [
            presunto if len(row) > 1 and row[1] == "BBB010101BBB" else row
            for row in SAMPLE_ROWS
        ]
        parsed = sat_69b.parse_list_69b(_csv_text(rows))
        self.assertEqual(parsed["BBB010101BBB"]["reference"], "500-05-DOF")

    def test_parse_rejects_missing_header(self):
        with self.assertRaises(sat_69b.SatListError):
            sat_69b.parse_list_69b("no header here\n1,AAA,Name,Definitivo\n")

    def test_reference_unknown_status_is_empty(self):
        self.assertEqual(sat_69b._reference_from_row(["a", "b"], "Desconocido"), "")

    def test_load_list_caches_and_refreshes(self):
        calls = {"count": 0}

        def get(url, headers=None, timeout=None):
            calls["count"] += 1
            self.assertEqual(url, sat_69b.LIST_URL)
            self.assertIn("User-Agent", headers)
            self.assertEqual(timeout, 60)
            return _Response(CSV.encode("cp1252"))

        first = sat_69b.load_list(get=get)
        second = sat_69b.load_list(get=get)
        self.assertEqual(calls["count"], 1)
        self.assertIn("AAA010101AAA", second)
        self.assertIs(first, second)

        sat_69b._cache["fetched_at"] = time.time() - sat_69b.CACHE_TTL - 5
        sat_69b.load_list(get=get)
        self.assertEqual(calls["count"], 2)

    def test_load_list_uses_requests_by_default(self):
        with patch.object(
            sat_69b.requests, "get", return_value=_Response(CSV.encode("cp1252"))
        ) as mocked:
            parsed = sat_69b.load_list()
        mocked.assert_called_once()
        self.assertIn("BBB010101BBB", parsed)

    def test_load_list_keeps_stale_cache_when_download_fails(self):
        sat_69b._cache["by_rfc"] = {
            "AAA010101AAA": {
                "name": "ACME",
                "status": "Definitivo",
                "reference": "500-05-1",
            }
        }
        sat_69b._cache["fetched_at"] = time.time() - sat_69b.CACHE_TTL - 5

        def get(url, headers=None, timeout=None):
            raise requests.ConnectionError("sat down")

        cached = sat_69b.load_list(get=get)
        self.assertEqual(cached["AAA010101AAA"]["reference"], "500-05-1")

    def test_load_list_keeps_stale_cache_when_csv_is_invalid(self):
        sat_69b._cache["by_rfc"] = {
            "AAA010101AAA": {"name": "A", "status": "Presunto", "reference": "R"}
        }
        sat_69b._cache["fetched_at"] = 0

        def get(url, headers=None, timeout=None):
            return _Response(b"not a sat file")

        cached = sat_69b.load_list(get=get)
        self.assertEqual(cached["AAA010101AAA"]["reference"], "R")

    def test_load_list_raises_without_cache(self):
        def get(url, headers=None, timeout=None):
            return _Response(b"", status_code=503)

        with self.assertRaises(sat_69b.SatListError):
            sat_69b.load_list(get=get)

        def bad_csv(url, headers=None, timeout=None):
            return _Response(b"nope")

        with self.assertRaises(sat_69b.SatListError):
            sat_69b.load_list(get=bad_csv)

    def test_lookup_ignores_generic_and_unknown_rfc(self):
        get = patch.object(sat_69b.requests, "get").start()
        self.addCleanup(patch.stopall)
        self.assertIsNone(sat_69b.lookup_taxpayer(""))
        self.assertIsNone(sat_69b.lookup_taxpayer("XAXX010101000"))
        self.assertIsNone(sat_69b.lookup_taxpayer("xexx-010101-000"))
        get.assert_not_called()

        def download(url, headers=None, timeout=None):
            return _Response(CSV.encode("cp1252"))

        self.assertIsNone(sat_69b.lookup_taxpayer("ZZZ010101ZZ9", get=download))
        found = sat_69b.lookup_taxpayer(" bbb-010101-bbb ", get=download)
        self.assertEqual(found["status"], "Presunto")
