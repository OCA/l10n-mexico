#!/usr/bin/env python3
"""Regenerate the ISR tariff CSVs from the official Annex 8 of the RMF.

The tariffs of article 96 LISR are published once a year in the DOF, as a PDF,
inside the annexes of the Resolución Miscelánea Fiscal. This reads that PDF and
writes the module data, so updating for a new year is running one command
against the new file rather than retyping 77 numbers.

It extracts only the tariffs that apply to salaries -- section B (withholdings:
daily, 7, 10 and 15 days, monthly) and section C (the yearly tariff used for the
annual adjustment). The rest of the annex covers other regimes.

Usage::

    pdftotext -layout Anexo-8-RMF-2026.pdf anexo8.txt
    python3 import_anexo8_pdf.py anexo8.txt --year 2026 \\
        --dof-publication 2026-12-28 --date-start 2026-01-01

The importer refuses to write a tariff that does not have exactly the expected
number of brackets, or whose brackets do not chain: a PDF layout change that
drops a row would otherwise ship a tariff with a hole in it, and a hole in a
tariff is a wrong withholding, not a crash.
"""

import argparse
import csv
import logging
import os
import re
from decimal import Decimal

_logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Heading -> (periodicity, human name). Matched against the section titles of
# the annex, which are stable across years even when the numbers change.
SECTIONS = [
    (
        r"en función de la cantidad de trabajo realizado y no de días laborados",
        "daily",
        "Tarifa diaria",
    ),
    (r"correspondan a un periodo de 7 días", "weekly", "Tarifa de 7 días"),
    (r"correspondan a un periodo de 10 días", "ten_day", "Tarifa de 10 días"),
    (r"correspondan a un periodo de 15 días", "fortnight", "Tarifa de 15 días"),
    (
        r"para el cálculo de los pagos provisionales mensuales a que se refieren los",
        "monthly",
        "Tarifa mensual",
    ),
    (
        r"para el cálculo del impuesto correspondiente al ejercicio de {year}",
        "annual",
        "Tarifa anual {year}",
    ),
]

EXPECTED_BRACKETS = 11

ROW = re.compile(
    r"^\s*([\d,]+\.\d{2})\s+([\d,]+\.\d{2}|En adelante)\s+"
    r"([\d,]+\.\d{2}|0)\s+([\d,]+\.\d{2})\s*$"
)


def _number(text):
    return Decimal(text.replace(",", ""))


def _find_section(lines, pattern):
    """Index of the line that starts the section *body*, or None.

    The annex opens with a table of contents that repeats every heading
    verbatim, so the first match is the index entry, not the section. Taking the
    last match lands in the body. Getting this wrong is silent rather than
    loud -- every section then reads the same first table in the document -- so
    `_reject_duplicates` checks the outcome as well.
    """
    compiled = re.compile(pattern)
    found = None
    for index, line in enumerate(lines):
        if compiled.search(line):
            found = index
    return found


def _read_brackets(lines, start):
    """Rows of the first table found after ``start``.

    Stops at the first blank stretch after the rows begin, so the next section's
    heading never bleeds in.
    """
    brackets, started, blanks = [], False, 0
    for line in lines[start:]:
        match = ROW.match(line)
        if match:
            started, blanks = True, 0
            lower, upper, fee, rate = match.groups()
            brackets.append(
                {
                    "lower_limit": _number(lower),
                    "upper_limit": "" if upper == "En adelante" else _number(upper),
                    "fixed_fee": _number(fee),
                    "rate": _number(rate),
                }
            )
        elif started:
            blanks += 1
            # Page furniture (the DOF header) splits tables; only a long gap
            # means the table really ended.
            if blanks > 6:
                break
    return brackets


def _validate(name, brackets):
    if len(brackets) != EXPECTED_BRACKETS:
        raise ValueError(
            f"{name}: found {len(brackets)} brackets, expected {EXPECTED_BRACKETS}; "
            f"the PDF layout probably changed and rows were missed"
        )
    for previous, current in zip(brackets, brackets[1:], strict=False):
        if previous["upper_limit"] == "":
            raise ValueError(f"{name}: an open bracket is not the last one")
        gap = current["lower_limit"] - previous["upper_limit"]
        if gap != Decimal("0.01"):
            raise ValueError(
                f"{name}: brackets do not chain at {previous['upper_limit']} -> "
                f"{current['lower_limit']}"
            )
    if brackets[-1]["upper_limit"] != "":
        raise ValueError(f"{name}: the last bracket must be open ended")


def _reject_duplicates(tariffs):
    """Two periodicities may never carry the same brackets.

    The tariffs are the daily one scaled and re-rounded by SAT, so no two of
    them coincide. If two do, the extractor read the same table twice -- which
    is what happens when a heading is matched in the table of contents instead
    of in the body.
    """
    seen = {}
    for _periodicity, name, brackets in tariffs:
        key = tuple(
            (b["lower_limit"], b["upper_limit"], b["fixed_fee"], b["rate"])
            for b in brackets
        )
        if key in seen:
            raise ValueError(
                f"{name} and {seen[key]} came out identical; the extractor read "
                f"the same table twice"
            )
        seen[key] = name


def extract(text_path, year):
    lines = open(text_path, encoding="utf-8").read().split("\n")
    tariffs = []
    for pattern, periodicity, label in SECTIONS:
        pattern = pattern.format(year=year)
        start = _find_section(lines, pattern)
        if start is None:
            raise ValueError(f"{periodicity}: section not found in the annex")
        brackets = _read_brackets(lines, start)
        name = label.format(year=year)
        _validate(name, brackets)
        tariffs.append((periodicity, name, brackets))
        _logger.info("%s: %s brackets", name, len(brackets))
    _reject_duplicates(tariffs)
    return tariffs


def write_csv(path, fieldnames, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def update_tariffs(text_path, year, dof_publication, date_start, date_end):
    tariffs = extract(text_path, year)

    tariff_rows, line_rows = [], []
    for periodicity, name, brackets in tariffs:
        xmlid = f"isr_tariff_{periodicity}_{year}"
        tariff_rows.append(
            {
                "id": xmlid,
                "name": name,
                "periodicity": periodicity,
                "date_start": date_start,
                "date_end": date_end,
                "dof_publication": dof_publication,
            }
        )
        for index, bracket in enumerate(brackets, start=1):
            line_rows.append(
                {
                    "id": f"{xmlid}_line_{index:02d}",
                    "tariff_id:id": f"l10n_mx_isr_tariffs.{xmlid}",
                    "lower_limit": bracket["lower_limit"],
                    "upper_limit": bracket["upper_limit"],
                    "fixed_fee": bracket["fixed_fee"],
                    "rate": bracket["rate"],
                }
            )

    write_csv(
        os.path.join(DATA_DIR, "l10n_mx.isr.tariff.csv"),
        ["id", "name", "periodicity", "date_start", "date_end", "dof_publication"],
        tariff_rows,
    )
    write_csv(
        os.path.join(DATA_DIR, "l10n_mx.isr.tariff.line.csv"),
        ["id", "tariff_id:id", "lower_limit", "upper_limit", "fixed_fee", "rate"],
        line_rows,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", help="Annex 8 converted with `pdftotext -layout`")
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--dof-publication", required=True)
    parser.add_argument("--date-start", required=True)
    parser.add_argument("--date-end", default="")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    update_tariffs(
        args.text,
        args.year,
        args.dof_publication,
        args.date_start,
        args.date_end,
    )


if __name__ == "__main__":
    main()
