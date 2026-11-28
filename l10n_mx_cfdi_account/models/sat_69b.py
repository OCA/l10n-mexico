import csv
import io
import json
import logging
from datetime import timedelta

import requests

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

SAT_69B_URL = (
    "https://wu1agsprosta001.blob.core.windows.net/agsc-publicaciones/"
    "Datos_abiertos/Documents_AGAFF/Listado_completo_69-B.csv"
)
SAT_69B_TIMEOUT = 60
SAT_69B_ATTACHMENT_NAME = "sat_listado_completo_69b.json"
SAT_69B_STALE_DAYS = 30
# The published CSV opens with a legal notice, a title and the column headers.
SAT_69B_CSV_HEADER_LINES = 3
SAT_69B_CSV_RFC_COLUMN = 1
SAT_69B_CSV_STATUS_COLUMN = 3


class Sat69b(models.AbstractModel):
    """Local copy of SAT list 69-B.

    The list is kept as a JSON ``ir.attachment`` (``{rfc: status}``), so it
    lives in the filestore, where Odoo can always write and every worker sees
    the same copy. satcfdi keeps its own copy inside its package directory,
    which the Odoo user usually cannot write to.
    """

    _name = "l10n_mx_cfdi_account.sat_69b"
    _description = "SAT list 69-B"

    @api.model
    def _attachment(self):
        return (
            self.env["ir.attachment"]
            .sudo()
            .search(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "=", 0),
                    ("name", "=", SAT_69B_ATTACHMENT_NAME),
                ],
                order="id desc",
                limit=1,
            )
        )

    @api.model
    def _download(self):
        """Download the list from SAT and return it as ``{rfc: status}``."""
        response = requests.get(SAT_69B_URL, timeout=SAT_69B_TIMEOUT)
        response.raise_for_status()
        lines = io.StringIO(response.content.decode("windows-1250"))
        for _line in range(SAT_69B_CSV_HEADER_LINES):
            lines.readline()
        listing = {}
        for row in csv.reader(lines):
            if len(row) <= SAT_69B_CSV_STATUS_COLUMN:
                continue
            rfc = row[SAT_69B_CSV_RFC_COLUMN].strip().upper()
            status = row[SAT_69B_CSV_STATUS_COLUMN].strip()
            if rfc and status:
                listing[rfc] = status
        if not listing:
            raise ValueError("SAT list 69-B was downloaded empty")
        return listing

    @api.model
    def _refresh(self):
        """Download the list and store it, replacing the previous copy."""
        listing = self._download()
        raw = json.dumps(listing, ensure_ascii=False, separators=(",", ":")).encode()
        attachment = self._attachment()
        if attachment:
            attachment.raw = raw
        else:
            self.env["ir.attachment"].sudo().create(
                {
                    "name": SAT_69B_ATTACHMENT_NAME,
                    "res_model": self._name,
                    "res_id": 0,
                    "mimetype": "application/json",
                    "raw": raw,
                }
            )
        _logger.info("SAT list 69-B refreshed: %d taxpayers", len(listing))
        return listing

    @api.model
    def _cron_refresh(self):
        companies = self.env["res.company"].sudo()
        if not companies.search_count([("l10n_mx_cfdi_sat_69b_check", "=", True)]):
            return
        try:
            self._refresh()
        except Exception:
            # Keep the previous copy; the next run tries again.
            _logger.exception("Could not refresh SAT list 69-B")

    @api.model
    def _status(self, rfc):
        """Return the 69-B status of ``rfc``, or None if it is not listed.

        The stored copy is used when there is one, even if the scheduled
        refresh has been failing: an old list is better than refusing to
        invoice. With no copy yet, the list is downloaded on the spot.
        """
        attachment = self._attachment()
        if not attachment:
            return self._refresh().get(rfc)
        age = fields.Datetime.now() - attachment.write_date
        if age > timedelta(days=SAT_69B_STALE_DAYS):
            _logger.warning(
                "SAT list 69-B was last refreshed %d days ago; check the "
                "scheduled action that refreshes it",
                age.days,
            )
        return json.loads(attachment.raw).get(rfc)
