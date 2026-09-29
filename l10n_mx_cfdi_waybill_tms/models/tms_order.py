# Copyright (C) 2026 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class TMSOrder(models.Model):
    _inherit = "tms.order"

    waybill_ids = fields.One2many(
        "l10n_mx_cfdi_waybill.waybill",
        "tms_order_id",
        string="Carta Porte",
    )
    waybill_count = fields.Integer(compute="_compute_waybill_count")

    @api.depends("waybill_ids")
    def _compute_waybill_count(self):
        for order in self:
            order.waybill_count = len(order.waybill_ids)

    def _l10n_mx_cfdi_waybill_required(self):
        parameter = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_mx_cfdi_waybill_tms.require_published_waybill")
        )
        return parameter in ("True", "true", "1")

    def _check_published_waybill(self):
        if not self._l10n_mx_cfdi_waybill_required():
            return
        for order in self:
            if order._trip_operation() != "cargo":
                continue
            published = order.waybill_ids.filtered(
                lambda waybill: waybill.state == "published"
            )
            if not published:
                raise UserError(
                    self.env._(
                        "Publish the Carta Porte before starting this cargo trip."
                    )
                )

    def button_start_order(self):
        result = super().button_start_order()
        self._check_published_waybill()
        return result

    def action_create_waybill(self):
        self.ensure_one()
        if self._trip_operation() != "cargo":
            raise UserError(self.env._("Carta Porte is available for cargo trips."))
        existing = self.waybill_ids.filtered(
            lambda waybill: waybill.state != "canceled"
        )
        if existing:
            return self._action_open_waybills(existing)
        self._check_waybill_ready()
        waybill = self.env["l10n_mx_cfdi_waybill.waybill"].create(
            self._prepare_waybill_values()
        )
        entry_model = self.env["l10n_mx_cfdi_waybill.waybill_entry"]
        for cargo in self.cargo_ids:
            entry_model.create(self._prepare_waybill_entry_values(waybill, cargo))
        return self._action_open_waybills(waybill)

    def action_open_waybills(self):
        self.ensure_one()
        return self._action_open_waybills(self.waybill_ids)

    def _check_waybill_ready(self):
        self.ensure_one()
        if not self.vehicle_id:
            raise UserError(
                self.env._("Assign a vehicle before creating the Carta Porte.")
            )
        if not self.vehicle_id.l10n_mx_cfdi_waybill_vehicle_id:
            raise UserError(
                self.env._(
                    "Link the truck to a Carta Porte vehicle before creating "
                    "the waybill."
                )
            )
        if not self.driver_id:
            raise UserError(
                self.env._("Assign a driver before creating the Carta Porte.")
            )
        if not self.origin_id or not self.destination_id:
            raise UserError(
                self.env._(
                    "Set the origin and destination before creating the Carta Porte."
                )
            )
        if not self.cargo_ids:
            raise UserError(
                self.env._("Add the cargo before creating the Carta Porte.")
            )

    def _prepare_waybill_values(self):
        self.ensure_one()
        waybill_model = self.env["l10n_mx_cfdi_waybill.waybill"]
        values = waybill_model.with_context(
            active_model="tms.order", active_id=self.id
        ).default_get(["type", "receiver_id", "issuer_id", "name"])
        if not values.get("issuer_id"):
            issuer = self.env["l10n_mx_cfdi.issuer"].search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("registered", "=", True),
                ],
                limit=1,
            )
            values["issuer_id"] = issuer.id
        values.update(
            {
                "type": values.get("type") or "T",
                "tms_order_id": self.id,
                "receiver_id": values.get("receiver_id")
                or self.company_id.partner_id.id,
                "vehicle_id": self.vehicle_id.l10n_mx_cfdi_waybill_vehicle_id.id,
                "transporter_ids": [
                    (6, 0, self.driver_id._l10n_mx_cfdi_ensure_transporter().ids)
                ],
            }
        )
        self._l10n_mx_cfdi_sync_waybill_trailers()
        return values

    def _l10n_mx_cfdi_sync_waybill_trailers(self):
        self.ensure_one()
        cfdi_vehicle = self.vehicle_id.l10n_mx_cfdi_waybill_vehicle_id
        if not cfdi_vehicle:
            return
        trailers = self.equipment_ids.filtered(
            lambda line: line.role == "trailer" and not line.dropped
        ).vehicle_id
        waybill_trailers = self.env["l10n_mx_cfdi_waybill.vehicle_trailer"]
        for trailer in trailers:
            waybill_trailers |= trailer._l10n_mx_cfdi_ensure_waybill_trailer()
        if waybill_trailers:
            cfdi_vehicle.trailers = waybill_trailers

    def _prepare_waybill_entry_values(self, waybill, cargo):
        self.ensure_one()
        departure = self.scheduled_date_start or fields.Datetime.now()
        duration = self.scheduled_duration or 1.0
        return {
            "waybill_id": waybill.id,
            "cargo_id": cargo.id,
            "product_qty": cargo.quantity or 1.0,
            "origin_address_id": self.origin_id.id,
            "destination_address_id": self.destination_id.id,
            "departure_datetime": departure,
            "duration": duration,
            "arrival_datetime": departure + timedelta(hours=duration),
            "distance": 1.0,
        }

    def _action_open_waybills(self, waybills):
        action = {
            "type": "ir.actions.act_window",
            "name": self.env._("Carta Porte"),
            "res_model": "l10n_mx_cfdi_waybill.waybill",
            "target": "current",
        }
        if len(waybills) == 1:
            action.update({"view_mode": "form", "res_id": waybills.id})
        else:
            action.update(
                {
                    "view_mode": "list,form",
                    "domain": [("id", "in", waybills.ids)],
                }
            )
        return action
