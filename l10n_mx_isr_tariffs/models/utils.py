from odoo import fields
from odoo.exceptions import UserError, ValidationError


def required_date(record, date):
    """Reject a missing date instead of quietly using today's.

    A payslip is taxed with the tariff of *its* date. Falling back to today
    would return a number that looks right and is computed from the wrong year
    as soon as the tariffs are updated.
    """
    parsed = fields.Date.to_date(date)
    if not parsed:
        raise UserError(
            record.env._(
                "Falta la fecha. La tarifa, la UMA y el subsidio se resuelven por "
                "fecha, así que no se puede asumir la de hoy."
            )
        )
    return parsed


def check_no_overlap(records, key_fields=()):
    """Refuse two validity windows that cover the same day.

    The lookups take the newest window that matches and stop, so an accidental
    overlap does not raise: it silently changes which value is used. The place
    to catch that is on write.
    """
    for record in records:
        domain = [("id", "!=", record.id)]
        for field in key_fields:
            domain.append((field, "=", record[field]))
        domain += [
            "|",
            ("date_end", "=", False),
            ("date_end", ">", record.date_start),
        ]
        if record.date_end:
            domain.append(("date_start", "<", record.date_end))
        clash = record.search(domain, limit=1)
        if clash:
            raise ValidationError(
                record.env._(
                    "El periodo de vigencia se solapa con %(other)s.",
                    other=clash.display_name,
                )
            )
