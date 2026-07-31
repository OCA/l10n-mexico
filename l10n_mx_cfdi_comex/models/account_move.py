# Copyright (C) 2026 Open Source Integrators
# License GPL-3.0 or later (http://www.gnu.org/licenses/gpl).

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services import cce_builder


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_mx_cfdi_cce_enabled = fields.Boolean(
        string="Comercio Exterior (CCE)",
        help=(
            "Enable Complemento Comercio Exterior 2.0 on this invoice. "
            "Sets Exportacion=02 and attaches the CCE complement."
        ),
    )
    l10n_mx_cfdi_cce_clave_pedimento = fields.Char(
        string="Clave de pedimento",
        default="A1",
        help="SAT c_ClavePedimento code (e.g. A1 for definitive export).",
    )
    l10n_mx_cfdi_cce_certificado_origen = fields.Selection(
        selection=[
            ("0", "Does not act as certificate of origin"),
            ("1", "Acts as certificate of origin"),
        ],
        string="Certificado de origen",
        default="0",
    )
    l10n_mx_cfdi_cce_num_certificado_origen = fields.Char(
        string="Número certificado de origen",
    )
    l10n_mx_cfdi_cce_tipo_cambio_usd = fields.Float(
        string="Tipo cambio USD",
        digits=(16, 6),
        help=(
            "MXN per 1 USD (SAT TipoCambioUSD). Prefer Banxico rate for "
            "the invoice date."
        ),
    )
    l10n_mx_cfdi_cce_total_usd = fields.Float(
        string="Total USD",
        digits=(16, 2),
        compute="_compute_l10n_mx_cfdi_cce_total_usd",
        store=True,
        readonly=False,
    )
    l10n_mx_cfdi_cce_motivo_traslado = fields.Char(
        string="Motivo de traslado",
        help="SAT c_MotivoTraslado when applicable.",
    )
    l10n_mx_cfdi_cce_observaciones = fields.Char(string="Observaciones CCE")
    l10n_mx_cfdi_cce_numero_exportador_confiable = fields.Char(
        string="Número exportador confiable",
    )
    l10n_mx_cfdi_cce_destinatario_id = fields.Many2one(
        "res.partner",
        string="Destinatario CCE",
        help=(
            "Optional goods recipient when different from the CFDI receptor. "
            "Address is taken from the partner."
        ),
    )

    @api.depends(
        "invoice_line_ids.l10n_mx_cfdi_cce_valor_dolares",
        "invoice_line_ids.display_type",
        "l10n_mx_cfdi_cce_enabled",
    )
    def _compute_l10n_mx_cfdi_cce_total_usd(self):
        for move in self:
            if not move.l10n_mx_cfdi_cce_enabled:
                move.l10n_mx_cfdi_cce_total_usd = 0.0
                continue
            total = sum(
                line.l10n_mx_cfdi_cce_valor_dolares
                for line in move.invoice_line_ids
                if line.display_type == "product" and line.product_id
            )
            move.l10n_mx_cfdi_cce_total_usd = total

    def _l10n_mx_cfdi_invoice_exportacion_complemento(self):
        self.ensure_one()
        if not self.l10n_mx_cfdi_cce_enabled:
            return super()._l10n_mx_cfdi_invoice_exportacion_complemento()
        self._l10n_mx_cfdi_cce_validate()
        return "02", cce_builder.build_comercio_exterior_from_invoice(self)

    def _l10n_mx_cfdi_cce_validate(self):
        """Raise UserError when required CCE fields are missing."""
        self.ensure_one()
        errors = []
        if not self.l10n_mx_cfdi_cce_clave_pedimento:
            errors.append(self.env._("- Clave de pedimento is required for CCE."))
        if not self.l10n_mx_cfdi_cce_tipo_cambio_usd:
            errors.append(self.env._("- Tipo cambio USD is required for CCE."))
        if not self.invoice_incoterm_id:
            errors.append(
                self.env._(
                    "- Incoterm is required for CCE "
                    "(set it on the invoice Other Info tab)."
                )
            )
        if not self.l10n_mx_cfdi_cce_total_usd:
            errors.append(
                self.env._(
                    "- Total USD must be greater than zero "
                    "(set Valor dólares on invoice lines)."
                )
            )

        issuer_partner = self.issuer_id.partner_id if self.issuer_id else False
        if issuer_partner:
            try:
                self._l10n_mx_cfdi_cce_partner_address(issuer_partner)
            except UserError as err:
                errors.append(
                    self.env._(
                        "- Issuer CCE address: %s",
                        err.args[0] if err.args else err,
                    )
                )
        else:
            errors.append(self.env._("- Issuer is required for CCE."))

        receptor = self.receiver_id or self.partner_id
        if receptor:
            try:
                self._l10n_mx_cfdi_cce_partner_address(receptor)
            except UserError as err:
                errors.append(
                    self.env._(
                        "- Receptor CCE address: %s",
                        err.args[0] if err.args else err,
                    )
                )
        else:
            errors.append(self.env._("- Receptor is required for CCE."))

        product_lines = self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product" and line.product_id
        )
        if not product_lines:
            errors.append(
                self.env._("- At least one product line is required for CCE.")
            )
        for line in product_lines:
            if not line.l10n_mx_cfdi_cce_valor_dolares:
                errors.append(
                    self.env._(
                        "- Line %s: Valor dólares is required for CCE.",
                        line.product_id.display_name,
                    )
                )
            if not (
                line.product_id.default_code or line.l10n_mx_cfdi_cce_no_identificacion
            ):
                errors.append(
                    self.env._(
                        "- Line %s: set a product Internal Reference "
                        "or No identificación for CCE.",
                        line.product_id.display_name,
                    )
                )
            fraccion = line.product_id.product_tmpl_id.l10n_mx_cfdi_tariff_code
            if not fraccion:
                errors.append(
                    self.env._(
                        "- Line %s: tariff code (fracción arancelaria) "
                        "is required on the product.",
                        line.product_id.display_name,
                    )
                )

        if (
            self.l10n_mx_cfdi_cce_certificado_origen == "1"
            and not self.l10n_mx_cfdi_cce_num_certificado_origen
        ):
            errors.append(
                self.env._(
                    "- Número certificado de origen is required when "
                    "Certificado de origen is set to 1."
                )
            )

        if errors:
            raise UserError(
                self.env._(
                    "Cannot build Comercio Exterior complement:\n%s",
                    "\n".join(errors),
                )
            )

    def _l10n_mx_cfdi_cce_map_country(self, country):
        """Map ``res.country`` to SAT ``c_pais``."""
        Pais = self.env["l10n_mx_catalogs.c_pais"]
        if not country:
            return Pais
        # Common ISO-3166-1 alpha-2 → SAT c_Pais (often alpha-3)
        iso2_to_sat = {
            "MX": "MEX",
            "US": "USA",
            "CA": "CAN",
            "CN": "CHN",
            "DE": "DEU",
            "ES": "ESP",
            "FR": "FRA",
            "GB": "GBR",
            "JP": "JPN",
            "BR": "BRA",
        }
        sat_code = iso2_to_sat.get(country.code) or country.code
        c_pais = Pais.search([("code", "=", sat_code)], limit=1)
        if c_pais:
            return c_pais
        if country.code == "MX":
            return self.env.ref("l10n_mx_catalogs.c_pais_MEX", raise_if_not_found=False)
        c_pais = Pais.map_res_country(country)
        if c_pais:
            return c_pais
        return Pais.search([("description", "ilike", country.name)], limit=1)

    def _l10n_mx_cfdi_cce_partner_address(self, partner):
        """Build a CCE domicilio dict from a partner address."""
        self.ensure_one()
        partner.ensure_one()
        c_pais = self._l10n_mx_cfdi_cce_map_country(partner.country_id)
        if not c_pais:
            raise UserError(
                self.env._(
                    "No SAT country code found for partner %s.",
                    partner.display_name,
                )
            )
        calle = (
            getattr(partner, "street_name", None) or partner.street or partner.street2
        )
        if not calle:
            raise UserError(
                self.env._(
                    "Street is required on partner %s for CCE domicilio.",
                    partner.display_name,
                )
            )
        if not partner.zip:
            raise UserError(
                self.env._(
                    "ZIP / Código postal is required on partner %s for CCE.",
                    partner.display_name,
                )
            )

        estado = False
        municipio = False
        localidad = False
        if c_pais.code == "MEX" and partner.zip:
            cp = self.env["l10n_mx_catalogs.c_codigo_postal"].search(
                [("code", "=", partner.zip)], limit=1
            )
            estado = cp.state_code or (
                partner.state_id.code if partner.state_id else False
            )
            municipio = cp.municipality_code or False
            localidad = cp.locality_code or False
        else:
            estado = partner.state_id.code if partner.state_id else partner.city
        if not estado:
            raise UserError(
                self.env._(
                    "State (Estado) is required on partner %s for CCE domicilio.",
                    partner.display_name,
                )
            )

        data = {
            "Calle": calle,
            "Estado": estado,
            "Pais": c_pais.code,
            "CodigoPostal": partner.zip,
            "NumeroExterior": getattr(partner, "street_number", None) or None,
            "NumeroInterior": getattr(partner, "street_number2", None) or None,
            "Localidad": localidad or partner.city or None,
            "Municipio": municipio or None,
            "Referencia": partner.street2 or None,
        }
        return {k: v for k, v in data.items() if v}

    def _l10n_mx_cfdi_cce_gather_mercancias(self):
        self.ensure_one()
        mercancias = []
        for line in self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product" and line.product_id
        ):
            fraccion = line.product_id.product_tmpl_id.l10n_mx_cfdi_tariff_code
            no_id = (
                line.l10n_mx_cfdi_cce_no_identificacion
                or line.product_id.default_code
                or str(line.id)
            )
            item = {
                "NoIdentificacion": no_id,
                "ValorDolares": line.l10n_mx_cfdi_cce_valor_dolares,
                "FraccionArancelaria": fraccion.code if fraccion else None,
            }
            cantidad = line.l10n_mx_cfdi_cce_cantidad_aduana or line.quantity
            if cantidad:
                item["CantidadAduana"] = cantidad
            if line.l10n_mx_cfdi_cce_unidad_aduana:
                item["UnidadAduana"] = line.l10n_mx_cfdi_cce_unidad_aduana
            if line.l10n_mx_cfdi_cce_valor_unitario_aduana:
                item["ValorUnitarioAduana"] = (
                    line.l10n_mx_cfdi_cce_valor_unitario_aduana
                )
            mercancias.append(item)
        return mercancias

    def _l10n_mx_cfdi_cce_gather_data(self):
        """Structured dict consumed by ``cce_builder``."""
        self.ensure_one()
        issuer_partner = self.issuer_id.partner_id
        receptor = self.receiver_id or self.partner_id
        data = {
            "ClaveDePedimento": self.l10n_mx_cfdi_cce_clave_pedimento,
            "CertificadoOrigen": int(self.l10n_mx_cfdi_cce_certificado_origen or "0"),
            "TipoCambioUSD": self.l10n_mx_cfdi_cce_tipo_cambio_usd,
            "TotalUSD": self.l10n_mx_cfdi_cce_total_usd,
            "Incoterm": (
                self.invoice_incoterm_id.code if self.invoice_incoterm_id else None
            ),
            "Observaciones": self.l10n_mx_cfdi_cce_observaciones or None,
            "MotivoTraslado": self.l10n_mx_cfdi_cce_motivo_traslado or None,
            "NumCertificadoOrigen": self.l10n_mx_cfdi_cce_num_certificado_origen
            or None,
            "NumeroExportadorConfiable": (
                self.l10n_mx_cfdi_cce_numero_exportador_confiable or None
            ),
            "Mercancias": self._l10n_mx_cfdi_cce_gather_mercancias(),
            "Emisor": {
                "Domicilio": self._l10n_mx_cfdi_cce_partner_address(issuer_partner)
            },
            "Receptor": {
                "NumRegIdTrib": (
                    receptor.vat if receptor.country_id.code != "MX" else None
                ),
                "Domicilio": self._l10n_mx_cfdi_cce_partner_address(receptor),
            },
        }
        if self.l10n_mx_cfdi_cce_destinatario_id:
            dest = self.l10n_mx_cfdi_cce_destinatario_id
            data["Destinatario"] = {
                "Nombre": dest.name,
                "NumRegIdTrib": dest.vat or None,
                "Domicilio": self._l10n_mx_cfdi_cce_partner_address(dest),
            }
        return data
