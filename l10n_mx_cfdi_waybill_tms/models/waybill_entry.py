# Copyright (C) 2026 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import fields, models
from odoo.exceptions import ValidationError


class WaybillEntry(models.Model):
    _inherit = "l10n_mx_cfdi_waybill.waybill_entry"

    cargo_id = fields.Many2one("tms.cargo", string="Cargo", ondelete="set null")

    def _compute_addresses_times_and_distance(self):
        cargo_entries = self.filtered("cargo_id")
        result = super(
            WaybillEntry, self - cargo_entries
        )._compute_addresses_times_and_distance()
        for entry in cargo_entries:
            trip = entry.cargo_id.order_id
            if trip.origin_id and not entry.origin_address_id:
                entry.origin_address_id = trip.origin_id
            if trip.destination_id and not entry.destination_address_id:
                entry.destination_address_id = trip.destination_id
            if trip.scheduled_date_start and not entry.departure_datetime:
                entry.departure_datetime = trip.scheduled_date_start
            if not entry.distance:
                entry.distance = 1.0
            if not entry.duration:
                entry.duration = trip.scheduled_duration or 1.0
            if entry.departure_datetime and not entry.arrival_datetime:
                entry.arrival_datetime = entry.departure_datetime + timedelta(
                    hours=entry.duration
                )
        return result

    def _validate_required_fields(self):
        cargo_entries = self.filtered("cargo_id")
        result = super(WaybillEntry, self - cargo_entries)._validate_required_fields()
        for entry in cargo_entries:
            entry._validate_cargo_fields()
        return result

    def _validate_cargo_fields(self):
        self.ensure_one()
        cargo = self.cargo_id
        if not self.origin_address_id or not self.destination_address_id:
            raise ValidationError(
                self.env._("Set the origin and destination on the trip.")
            )
        if self.origin_address_id.country_id != self.destination_address_id.country_id:
            raise ValidationError(
                self.env._("Origin and destination must be in the same country.")
            )
        if not self.departure_datetime or not self.arrival_datetime:
            raise ValidationError(
                self.env._("Set the departure and arrival on the Carta Porte line.")
            )
        if not self.distance:
            raise ValidationError(
                self.env._("Set the distance on the Carta Porte line.")
            )
        if not cargo.l10n_mx_cfdi_product_code_id:
            raise ValidationError(
                self.env._("Set the SAT product code on the cargo line: %s", cargo.name)
            )
        if not cargo.l10n_mx_cfdi_unit_id:
            raise ValidationError(
                self.env._("Set the SAT unit on the cargo line: %s", cargo.name)
            )
        if not cargo._l10n_mx_cfdi_weight_kg():
            raise ValidationError(
                self.env._("Set the weight on the cargo line: %s", cargo.name)
            )
        published = self.search(
            [
                ("cargo_id", "=", cargo.id),
                ("id", "!=", self.id),
                ("waybill_id.state", "=", "published"),
            ]
        )
        if published:
            raise ValidationError(
                self.env._(
                    'Cargo "%(cargo)s" is already on the published Carta Porte '
                    '"%(waybill)s".',
                    cargo=cargo.name,
                    waybill=published.waybill_id[:1].name,
                )
            )
