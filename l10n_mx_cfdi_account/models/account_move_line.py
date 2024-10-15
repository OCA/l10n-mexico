from odoo import api, fields, models
from odoo.tools import float_is_zero, float_round, json_float_round


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    cfdi_price_unit = fields.Monetary(
        compute="_compute_cfdi_fields",
        store=True,
    )

    cfdi_subtotal = fields.Monetary(
        compute="_compute_cfdi_fields",
        store=True,
    )

    cfdi_discount = fields.Monetary(
        compute="_compute_cfdi_fields",
        store=True,
    )

    @api.depends(
        "product_id",
        "price_unit",
        "quantity",
        "discount",
    )
    def _compute_cfdi_fields(self):
        for line in self:
            line._gater_cfdi_item_data()

    def _gater_cfdi_item_data(self):
        self.ensure_one()

        res = {}
        currency = self.currency_id.sudo()

        # use product price decimal precision to round the price calculations
        price_decimal_precision = self.env.ref("product.decimal_price").sudo().digits

        # Compute 'Subtotal'.
        line_discount_price_unit = self.price_unit

        if hasattr(self, "discount_fixed"):
            line_discount_price_unit -= self.discount_fixed

        line_discount_price_unit = line_discount_price_unit * (
            1 - self.discount / 100.0
        )
        # round the price unit to the currency precision to prevent
        # differences between the invoice totals and the CFDI total
        line_discount_price_unit = float_round(
            line_discount_price_unit, precision_digits=price_decimal_precision
        )

        subtotal = self.quantity * line_discount_price_unit

        # keep track of taxes included in price to subtract them later
        # from the unit price as the CFDI specification doesn't support
        # then
        taxes_included = 0

        cfdi_taxes = []
        if self.tax_ids:
            # Compute taxes and adjust 'Subtotal' and 'Total'
            taxes = self.tax_ids._origin.with_context(force_sign=1)
            taxes_res = taxes.compute_all(
                line_discount_price_unit,
                quantity=self.quantity,
                currency=self.currency_id,
                product=self.product_id,
                partner=self.partner_id,
                is_refund=self.move_id.move_type in ("out_refund", "in_refund"),
            )
            res["Subtotal"] = taxes_res["total_excluded"]
            res["Total"] = taxes_res["total_included"]

            for computed_tax in taxes_res["taxes"]:
                tax_id = self.env["account.tax"].browse(computed_tax["id"])
                tax_rate = (
                    tax_id.amount / 100
                    if tax_id.amount_type == "percent"
                    else tax_id.amount
                )
                is_retention = tax_id.extract_is_retention()
                tax_rate = json_float_round(tax_rate, precision_digits=6)
                tax_total = json_float_round(
                    computed_tax["amount"], precision_digits=currency.decimal_places
                )
                tax_base = json_float_round(
                    taxes_res["total_excluded"],
                    precision_digits=currency.decimal_places,
                )

                # SAT requires positive retention taxes, but Odoo uses negative values.
                if is_retention:
                    tax_rate *= -1
                    tax_total *= -1

                cfdi_taxes.append(
                    {
                        "Name": tax_id.extract_l10n_mx_tax_code(),
                        "Rate": tax_rate,
                        "IsRetention": is_retention,
                        "Base": tax_base,
                        "Total": tax_total,
                    }
                )

                if tax_id.price_include:
                    taxes_included += tax_total

        if cfdi_taxes:
            res.update(
                {
                    "Taxes": cfdi_taxes,
                    "TaxObject": "02",  # 'Si objeto de impuesto'
                }
            )
        else:
            res["Total"] = res["Subtotal"] = subtotal
            res["TaxObject"] = "01"

        if self.product_id.default_code:
            res["IdentificationNumber"] = self.product_id.default_code
        unit_included_taxes = taxes_included / (self.quantity or 1)
        line_discount_price_unit -= unit_included_taxes
        res.update(
            {
                "Quantity": self.quantity,
                "ProductCode": self.product_id.l10n_mx_cfdi_product_code_id.code,
                "Description": self.name,
                "UnitCode": self.product_id.l10n_mx_cfdi_product_measurement_unit_id.code,
            }
        )

        self._round_values_to_currency_precision(res)

        # compute discount
        expected_subtotal_wo_discount = line_discount_price_unit * self.quantity
        discount = (
            (self.price_unit * self.quantity)
            - expected_subtotal_wo_discount
            - taxes_included
        )
        if float_is_zero(discount, precision_digits=currency.decimal_places):
            # ignore a difference below the currency precision
            discount = 0

        res["Discount"] = discount
        res["Subtotal"] += discount

        # recompute the unit price from the subtotal to avoid rounding
        res["UnitPrice"] = res["Subtotal"] / (self.quantity or 1)

        self._round_values_to_currency_precision(res)

        # store the values to be used in the report
        self.cfdi_subtotal = res["Subtotal"]
        self.cfdi_discount = res["Discount"]
        self.cfdi_price_unit = res["UnitPrice"]

        return res

    def _round_values_to_currency_precision(self, res, skip=None):
        currency_decimal_places = self.currency_id.decimal_places

        # Round all values to the currency precision
        for k, v in res.items():
            if skip and k in skip:
                continue

            if isinstance(v, float):
                res[k] = json_float_round(v, precision_digits=currency_decimal_places)
            else:
                res[k] = v
