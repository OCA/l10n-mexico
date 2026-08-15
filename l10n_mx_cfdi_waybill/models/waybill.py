import re
from datetime import timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class Waybill(models.Model):
    _name = "l10n_mx_cfdi_waybill.waybill"
    _description = "waybill (Carta Porte)"
    _inherits = {"l10n_mx_cfdi.document": "cfdi_id"}
    _inherit = ["mail.thread", "mail.activity.mixin"]

    cfdi_id = fields.Many2one(
        "l10n_mx_cfdi.document", string="CFDI", ondelete="cascade", required=True
    )

    federal_highway_use = fields.Boolean(
        string="Uso de carretera federal", default=True
    )

    vehicle_id = fields.Many2one("l10n_mx_cfdi_waybill.vehicle", string="Vehículo")
    transporter_ids = fields.Many2many(
        "l10n_mx_cfdi_waybill.transporter",
        string="Contactos",
        relation="l10n_mx_cfdi_waybill_waybill_transporter_rel",
    )

    entry_ids = fields.One2many(
        "l10n_mx_cfdi_waybill.waybill_entry",
        "waybill_id",
        string="Entradas",
        readonly=False,
    )

    picking_ids = fields.Many2many(
        "stock.picking",
        string="Traslados",
        relation="stock_picking_waybill_rel",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        context = self.env.context

        # set CFDI type to "T" (traslado)
        res["type"] = "T"

        company_contact = self.env.company.partner_id
        res["receiver_id"] = company_contact.id

        issuer_id = self.env["l10n_mx_cfdi.issuer"].search(
            [
                "&",
                ("company_id", "=", self.env.company.id),
                ("registered", "=", "True"),
            ],
            limit=1,
        )
        res["issuer_id"] = issuer_id.id

        # load data from stock.picking if available
        if context.get("active_model") == "stock.picking":
            picking_ids = self.env["stock.picking"].browse(
                context.get("active_ids", [])
            )
            res["picking_ids"] = picking_ids

            if picking_ids.picking_type_id.code == "outgoing":
                res["receiver_id"] = picking_ids.partner_id.id
            else:
                res["receiver_id"] = issuer_id.partner_id.id

        res["name"] = "(Borrador)"

        return res

    @api.onchange("picking_ids")
    def _onchange_picking_ids(self):
        """Create missing entries for the entry_ids field"""
        self.ensure_one()

        if not self.picking_ids:
            return

        # ensure only one type of picking is selected
        if len(self.picking_ids.picking_type_id) > 1:
            raise ValidationError(
                self.env._("Solo se pueden seleccionar traslados del mismo tipo")
            )

        related_moves_ids = self.picking_ids.move_ids.ids or []
        existing_moves_ids = self.entry_ids.move_id.ids or []
        missing_moves = set(related_moves_ids) - set(existing_moves_ids)

        new_entries = self.env["l10n_mx_cfdi_waybill.waybill_entry"]
        for missing_move_id in missing_moves:
            new_entries |= self.entry_ids.create(
                {
                    "waybill_id": self.id,
                    "move_id": missing_move_id,
                }
            )

        self.entry_ids |= new_entries

    def action_post(self):
        self.ensure_one()

        self._validate_required_fields()
        self._assign_serial_number()
        data = self._format_data()
        from ..services import waybill_builder

        cfdi = waybill_builder.build_waybill_comprobante(self.issuer_id, data)

        # set issuer and receiver
        self.cfdi_id.update(
            {
                "issuer_id": self.issuer_id.id,
                "receiver_id": self.receiver_id.id,
            }
        )

        try:
            self.cfdi_id.publish(cfdi)
            for picking in self.picking_ids:
                picking.waybill_ids = [(4, self.id)]

            self.cfdi_id._compute_download_files_if_needed()
            # create attachments
            pdf_attachment = self.env["ir.attachment"].create(
                {
                    "name": self.cfdi_id.pdf_filename,
                    "datas": self.cfdi_id.pdf_file,
                    "res_model": "l10n_mx_cfdi_waybill.waybill",
                    "res_id": self.id,
                    "type": "binary",
                }
            )

            xml_attachment = self.env["ir.attachment"].create(
                {
                    "name": self.cfdi_id.xml_filename,
                    "datas": self.cfdi_id.xml_file,
                    "res_model": "l10n_mx_cfdi_waybill.waybill",
                    "res_id": self.id,
                    "type": "binary",
                }
            )

            # add post message with attachments
            self.message_post(
                body=self.env._("Se ha publicado el CFDI de la carta porte"),
                attachment_ids=[pdf_attachment.id, xml_attachment.id],
            )
        except Exception as e:
            raise UserError(str(e)) from e

    def _format_data(self):
        items_data = self._format_items_data()
        goods_data, locations_data = self._format_goods_and_locations_data()

        # NameId 36 is applied by satcfdi Facturama mapper when CartaPorte is present.
        data = {
            "CfdiType": "T",
            "ExpeditionPlace": self.issuer_id.zip,
            "Receiver": {
                "Name": self.receiver_id.name
                or self.issuer_id.fiscal_name
                or self.issuer_id.name,
                "Rfc": self.receiver_id.vat or self.issuer_id.vat,
                "CfdiUse": "S01",  # Sin efectos fiscales
                "FiscalRegime": (
                    self.receiver_id.tax_regime.code
                    if self.receiver_id.tax_regime
                    else self.issuer_id.tax_regime.code
                ),
                "TaxZipCode": self.receiver_id.zip or self.issuer_id.zip,
            },
            "Items": items_data,
            "Complemento": {
                "CartaPorte31": {
                    "TranspInternac": "No",
                    "Ubicaciones": locations_data,
                    "Mercancias": {
                        "UnidadPeso": "KGM",
                        "Mercancia": goods_data,
                    },
                }
            },
        }

        if self.federal_highway_use:
            self._add_autotransporte_data(data)
            self.self_add_figuratransporte_data(data)

        return data

    def _format_items_data(self):
        items_data = []
        for entry in self.entry_ids:
            item_data = self._format_invoice_item_data(entry)
            items_data.append(item_data)

        return items_data

    def _format_invoice_item_data(self, entry):
        product = entry.product_id
        item_data = {
            "ProductCode": product.l10n_mx_cfdi_product_code_id.code,
            "UnitCode": product.l10n_mx_cfdi_product_measurement_unit_id.code,
            "Description": product.name,
            "Quantity": entry.product_qty,
            "UnitPrice": 0,
            "Subtotal": 0,
            "Total": 0,
            "TaxObject": "01",  # No sujeto a impuestos
        }
        if product.default_code:
            item_data["IdentificationNumber"] = product.default_code
        return item_data

    def self_add_figuratransporte_data(self, data):
        figura_transporte = []
        for transporter in self.transporter_ids:
            item_data = {
                "TipoFigura": transporter.type.code,
                "RFCFigura": transporter.partner_id.vat,
                "NombreFigura": transporter.partner_id.name,
            }
            if transporter.type.code == "01":
                item_data["NumLicencia"] = transporter.driving_license

            if transporter.type.code == "02" or transporter.type.code == "03":
                item_data["PartesTransporte"] = [
                    {"ParteTransporte": parte_transporte.code}
                    for parte_transporte in transporter.parte_transporte_ids
                ]

            figura_transporte.append(item_data)

        data["Complemento"]["CartaPorte31"]["FiguraTransporte"] = figura_transporte

    def _add_autotransporte_data(self, data):
        data["Complemento"]["CartaPorte31"]["Mercancias"]["Autotransporte"] = {
            "PermSCT": self.vehicle_id.permit_type.code,
            "NumPermisoSCT": self.vehicle_id.permit_number,
            "IdentificacionVehicular": {
                "ConfigVehicular": self.vehicle_id.vehicle_setup.code,
                "PlacaVM": self.vehicle_id.plate,
                "AnioModeloVM": self.vehicle_id.model,
                "PesoBrutoVehicular": f"{self.vehicle_id.gross_vehicle_weight:.3f}",
            },
            "Seguros": {
                "AseguraRespCivil": self.vehicle_id.insurance_company.name,
                "PolizaRespCivil": self.vehicle_id.insurance_number,
            },
        }

    def _format_goods_and_locations_data(self):
        locations_data = []
        goods_data = []

        origin_locations_codes = {}
        destination_locations_codes = {}
        for idx, entry_id in enumerate(self.entry_ids):
            if entry_id.origin_address_id not in origin_locations_codes:
                origin_location_id = "OR" + str(idx + 1).zfill(6)
                origin_locations_codes[entry_id.origin_address_id] = origin_location_id

                # get departure date in user timezone
                tz = pytz.timezone(self.env.user.tz)
                departure_date = pytz.utc.localize(
                    entry_id.departure_datetime
                ).astimezone(tz)

                locations_data.append(
                    {
                        "TipoUbicacion": "Origen",
                        "IDUbicacion": origin_location_id,
                        "RFCRemitenteDestinatario": self.issuer_id.vat,
                        "FechaHoraSalidaLlegada": departure_date.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "DistanciaRecorrida": 0,
                        "Domicilio": self._format_address(entry_id.origin_address_id),
                    }
                )

            if entry_id.destination_address_id not in destination_locations_codes:
                destination_location_id = "DE" + str(idx + 1).zfill(6)
                destination_locations_codes[entry_id.destination_address_id] = (
                    destination_location_id
                )

                # get arrival date in user timezone
                tz = pytz.timezone(self.env.user.tz)
                arrival_date = pytz.utc.localize(entry_id.arrival_datetime).astimezone(
                    tz
                )

                locations_data.append(
                    {
                        "TipoUbicacion": "Destino",
                        "IDUbicacion": destination_location_id,
                        "RFCRemitenteDestinatario": self.issuer_id.vat,
                        "FechaHoraSalidaLlegada": arrival_date.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "DistanciaRecorrida": entry_id.distance,
                        "Domicilio": self._format_address(
                            entry_id.destination_address_id
                        ),
                    }
                )

        for _idx, entry_id in enumerate(self.entry_ids):
            data = self._format_goods_transport_details(
                entry_id, origin_locations_codes, destination_locations_codes
            )
            goods_data.append(data)

        return goods_data, locations_data

    def _format_goods_transport_details(
        self, entry_id, origin_locations_codes, destination_locations_codes
    ):
        origin_location_id = origin_locations_codes[entry_id.origin_address_id]
        destination_location_id = destination_locations_codes[
            entry_id.destination_address_id
        ]
        total_weight = entry_id.product_id.weight * entry_id.product_qty
        unit_code = entry_id.product_id.l10n_mx_cfdi_product_measurement_unit_id.code
        data = {
            "Cantidad": entry_id.product_qty,
            "BienesTransp": entry_id.product_id.l10n_mx_cfdi_product_code_id.code,
            "Descripcion": entry_id.product_id.name,
            "ClaveUnidad": unit_code,
            "PesoEnKg": f"{total_weight:.3f}",
            "CantidadTransporta": [
                {
                    "Cantidad": entry_id.product_qty,
                    "IDOrigen": origin_location_id,
                    "IDDestino": destination_location_id,
                }
            ],
        }
        return data

    def _map_partner_country_to_c_pais(self, country):
        c_pais = self.env["l10n_mx_catalogs.c_pais"].map_res_country(country)
        if c_pais:
            return c_pais
        if country.code == "MX":
            return self.env.ref("l10n_mx_catalogs.c_pais_MEX")
        return self.env["l10n_mx_catalogs.c_pais"].search(
            [("description", "ilike", country.name)],
            limit=1,
        )

    def _format_address(self, location):
        c_pais = self._map_partner_country_to_c_pais(location.country_id)
        if not c_pais:
            raise ValidationError(
                self.env._(
                    "No se encontró el código de país SAT para: %s",
                    location.country_id.name,
                )
            )
        if c_pais.code == "MEX":
            c_codigo_postal = self.env["l10n_mx_catalogs.c_codigo_postal"].search(
                [("code", "=", location.zip)], limit=1
            )
            data = {
                "Pais": c_pais.code,
                "CodigoPostal": location.zip,
                "Estado": c_codigo_postal.state_code or location.state_id.code,
                "Localidad": c_codigo_postal.locality_code or "",
                "Municipio": c_codigo_postal.municipality_code or "",
                "Referencia": location.street2 or "",
                "NumeroExterior": location.street_number or "",
                "NumeroInterior": location.street_number2 or "",
                "Calle": location.street_name or location.street,
            }
        else:
            data = {
                "Pais": c_pais.code,
                "CodigoPostal": location.zip,
                "Estado": location.state_id.code,
                "Calle": location.street,
                "Localidad": location.city,
                "NumeroExterior": location.street_number,
                "NumeroInterior": location.street_number2,
            }

        data = {k: v for k, v in data.items() if v}  # Remove empty values
        return data

    def _validate_required_fields(self):
        for rec in self:
            if rec.federal_highway_use:
                if not rec.vehicle_id:
                    raise ValidationError(
                        self.env._("Debe seleccionar un vehículo para la carta porte")
                    )

                rec.vehicle_id.validate()

                if not rec.transporter_ids:
                    raise ValidationError(
                        self.env._(
                            "Debe seleccionar al menos un transportista "
                            'en la sección "Contactos"'
                        )
                    )

                if not any(
                    transporter.type.code == "01" for transporter in rec.transporter_ids
                ):
                    raise ValidationError(
                        self.env._(
                            "Debe seleccionar al menos un transportista "
                            'con tipo "Operador"'
                        )
                    )

                for transporter in rec.transporter_ids:
                    if not transporter.partner_id.vat:
                        raise ValidationError(
                            self.env._(
                                "Debe ingresar el RFC del contact: %s",
                                transporter.partner_id.name,
                            )
                        )

                    if not transporter.type:
                        raise ValidationError(
                            self.env._(
                                "Debe seleccionar el tipo de contacto para: %s",
                                transporter.partner_id.name,
                            )
                        )

                    if not transporter.driving_license:
                        raise ValidationError(
                            self.env._(
                                "Debe ingresar el número de licencia del contact: %s",
                                transporter.partner_id.name,
                            )
                        )

            # ensure only one type of picking is selected
            if len(rec.picking_ids.picking_type_id) > 1:
                raise ValidationError(
                    self.env._("Solo se pueden seleccionar traslados del mismo tipo")
                )

            self.entry_ids._validate_required_fields()

    def action_cancel(self):
        # add cancellation message
        self.message_post(body=self.env._("Carta Porte cancelada"))

        # open wizard to cancel cfdi
        return {
            "name": "Cancelar Carta Porte",
            "type": "ir.actions.act_window",
            "res_model": "l10n_mx_cfdi_account.document_cancel",
            "view_mode": "form",
            "target": "new",
            "context": {"default_certificate_ids": [self.cfdi_id.id]},
        }

    def action_draft(self):
        self.state = "draft"

        # remove attachments
        self.env["ir.attachment"].search(
            [
                ("res_model", "=", "l10n_mx_cfdi_waybill.waybill"),
                ("res_id", "=", self.id),
            ]
        ).unlink()

    def action_print(self):
        # get attachments
        attachments = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "l10n_mx_cfdi_waybill.waybill"),
                ("res_id", "=", self.id),
                ("name", "ilike", self.pdf_filename),
            ]
        )

        if attachments:
            return {
                "name": "Carta Porte",
                "type": "ir.actions.act_url",
                "url": f"/web/content/{attachments[0].id}?download=true",
                "target": "new",
            }

    ###
    # Report Utils
    ###

    def format_address_for_report(self, address):
        """Transform address struct to a string for report."""

        result = address["Calle"]
        result += (
            " " + address["NumeroExterior"] if address.get("NumeroExterior") else ""
        )
        result += (
            " " + address["NumeroInterior"] if address.get("NumeroInterior") else ""
        )
        result += ", " + address["Estado"] if address.get("Estado") else ""
        result += ", " + address["Pais"] if address.get("Pais") else ""
        result += (
            ", C.P. " + address.get("CodigoPostal")
            if address.get("CodigoPostal")
            else ""
        )
        return result

    def format_peso_bruto_total(self, goods_data):
        """Transform goods_data to a string for report."""

        total = 0
        for good in goods_data:
            total += float(good["PesoEnKg"])

        return f"{total:.3f}"

    def _assign_serial_number(self):
        """Fetch next sequence and assign it"""

        # get or create sequence for CP
        sequence = (
            self.env["ir.sequence"]
            .sudo()
            .search(
                [
                    ("code", "=", "l10n_mx_cfdi_waybill.sequence"),
                ],
                limit=1,
            )
        )
        if not sequence:
            sequence = (
                self.env["ir.sequence"]
                .sudo()
                .create(
                    {
                        "code": "l10n_mx_cfdi_waybill.sequence",
                        "name": "Waybill Sequence",
                        "prefix": "CP/%(year)s/%(month)s/",
                    }
                )
            )

        name = sequence.next_by_id()
        serie = re.match(r"CP/\d{4}/\d{2}/", name).group(0)
        serie = re.sub(r"\W+", "", serie)

        self.cfdi_id.serie = serie
        self.cfdi_id.folio = re.match(r"CP/\d{4}/\d{2}/(\d+)", name).group(
            1
        )  # extract number as folio


class WaybillEntry(models.Model):
    _name = "l10n_mx_cfdi_waybill.waybill_entry"
    _description = "CFDI Goods Transfer"

    waybill_id = fields.Many2one(
        "l10n_mx_cfdi_waybill.waybill", "Carta porte", ondelete="cascade"
    )
    move_id = fields.Many2one("stock.move", "Movimiento")
    picking_id = fields.Many2one("stock.picking", "Traslado")
    product_id = fields.Many2one("product.product", "Producto")
    product_qty = fields.Float("Cantidad")

    @api.depends("move_id")
    def _compute_addresses_times_and_distance(self):
        for entry in self:
            entry.update(entry._get_defaults(entry.picking_id))
            if entry.origin_address_id and entry.destination_address_id:
                entry._compute_route_details()
                entry._compute_arrival_datetime()

    @api.depends("move_id")
    def _copy_moved_id_fields(self):
        for entry in self:
            if entry.move_id:
                entry.write(
                    {
                        "product_id": entry.move_id.product_id.id,
                        "product_qty": entry.move_id.product_uom_qty,
                        "picking_id": entry.move_id.picking_id.id,
                    }
                )

    origin_address_id = fields.Many2one(
        "res.partner",
        "Origen",
        default=lambda self: self._compute_addresses_times_and_distance(),
    )
    destination_address_id = fields.Many2one(
        "res.partner",
        "Destino",
        default=lambda self: self._compute_addresses_times_and_distance(),
    )

    departure_datetime = fields.Datetime(
        "Salida", default=lambda self: self._compute_addresses_times_and_distance()
    )
    arrival_datetime = fields.Datetime(
        "Arribo", default=lambda self: self._compute_addresses_times_and_distance()
    )

    distance = fields.Float("Distancia (Km)")
    duration = fields.Float("Duración (Hrs)")

    @api.model
    def create(self, vals_list):
        res = super().create(vals_list)
        res._compute_addresses_times_and_distance()
        res._copy_moved_id_fields()

        return res

    @api.model
    def _get_defaults(self, picking_id):
        res = {}
        if picking_id:
            if picking_id.location_id.warehouse_id:
                res["origin_address_id"] = (
                    picking_id.location_id.warehouse_id.partner_id.id
                )
            else:
                res["origin_address_id"] = picking_id.partner_id.id

            if picking_id.location_dest_id.warehouse_id:
                res["destination_address_id"] = (
                    picking_id.location_dest_id.warehouse_id.partner_id.id
                )
            else:
                res["destination_address_id"] = picking_id.partner_id.id

            if picking_id.scheduled_date:
                res["departure_datetime"] = picking_id.scheduled_date

        return res

    def _validate_required_fields(self):  # noqa: C901
        for entry in self:
            if not entry.origin_address_id:
                raise ValidationError(
                    self.env._(
                        "Debe seleccionar una dirección de origen "
                        "para el traslado de bienes"
                    )
                )

            if not entry.destination_address_id:
                raise ValidationError(
                    self.env._(
                        "Debe seleccionar una dirección de destino "
                        "para el traslado de bienes"
                    )
                )

            if (
                entry.origin_address_id.country_id
                != entry.destination_address_id.country_id
            ):
                raise UserError(
                    self.env._(
                        "La ubicación de origen y destino deben ser del mismo país."
                    )
                )

            if not entry.departure_datetime:
                raise ValidationError(
                    self.env._("Debe ingresar la fecha y hora de salida del traslado")
                )

            if not entry.arrival_datetime:
                raise ValidationError(
                    self.env._("Debe ingresar la fecha y hora de llegada del traslado")
                )

            if not entry.distance:
                raise ValidationError(
                    self.env._("Debe ingresar la distancia recorrida del traslado")
                )

            product_id = entry.product_id
            if not product_id.l10n_mx_cfdi_product_code_id:
                raise ValidationError(
                    self.env._(
                        "Debe ingresar el código del producto "
                        "en la ficha del producto: %s",
                        entry.product_id.name,
                    )
                )

            if not product_id.l10n_mx_cfdi_product_measurement_unit_id:
                raise ValidationError(
                    self.env._(
                        "Debe ingresar la unidad de medida del producto "
                        "en la ficha del producto: %s",
                        entry.product_id.name,
                    )
                )

            if not product_id.weight:
                raise ValidationError(
                    self.env._("Falta el campo Peso en: %s", entry.product_id.name)
                )

            if not entry.origin_address_id.zip:
                raise ValidationError(
                    self.env._(
                        "Falta el campo Código Postal en: %s",
                        entry.origin_address_id.name,
                    )
                )

            if not entry.destination_address_id.street:
                raise ValidationError(
                    self.env._(
                        "Falta el campo Calle en: %s", entry.destination_address_id.name
                    )
                )

            if not entry.destination_address_id.zip:
                raise ValidationError(
                    self.env._(
                        "Falta el campo Código Postal en: %s",
                        entry.destination_address_id.name,
                    )
                )

            if entry.move_id:
                # validate move is not already in a waybill
                related_cne = self.env["l10n_mx_cfdi_waybill.waybill_entry"].search(
                    [
                        ("move_id", "=", entry.move_id.id),
                    ]
                )

                for cn in related_cne.waybill_id:
                    if cn.state == "published":
                        raise ValidationError(
                            self.env._(
                                'La línea de traslado de "%(move)s" ya está incluido '
                                'en la carta porte "%(waybill)s"',
                                move=entry.move_id.display_name,
                                waybill=cn.name,
                            )
                        )

    @api.onchange("origin_address_id", "destination_address_id")
    def _compute_route_details(self):
        for entry in self:
            if not entry.origin_address_id or not entry.destination_address_id:
                continue

            if not entry.origin_address_id.date_localization:
                entry.origin_address_id.geo_localize()

            if not entry.destination_address_id.date_localization:
                entry.destination_address_id.geo_localize()

            geo_code = self.env["base.geocoder"]
            route = geo_code.geo_query_route(
                entry.origin_address_id,
                entry.destination_address_id,
            )

            if route:
                # convert meters to kilometers
                entry.distance = route.get("distance", 60000) / 1000

                # convert seconds to hours
                entry.duration = route.get("duration", 3600) / 3600
            else:
                entry.distance = 60
                entry.duration = 60

    @api.onchange("departure_datetime", "duration")
    def _compute_arrival_datetime(self):
        for entry in self:
            if entry.departure_datetime and entry.duration:
                entry.arrival_datetime = entry.departure_datetime + timedelta(
                    hours=entry.duration
                )
            else:
                entry.arrival_datetime = 0
