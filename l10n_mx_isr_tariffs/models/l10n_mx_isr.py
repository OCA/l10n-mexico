from odoo import models
from odoo.exceptions import UserError
from odoo.tools import float_round

# Periodicities whose tariff covers less than a month. The subsidy of such a
# payment has to be prorated by the days the period actually covers, and that
# number is a property of the period, not of its label: a fortnightly payroll
# runs 15 days in the first half of the month and 15 or 16 in the second.
SUB_MONTHLY = {"daily", "weekly", "ten_day", "fortnight"}


class Isr(models.AbstractModel):
    """The withholding calculation, composed from the two pieces.

    Kept apart from any payroll model on purpose: article 96 also governs
    payments assimilated to salaries, and the calculation is the same there.
    """

    _name = "l10n_mx.isr"
    _description = "Cálculo del ISR de sueldos y salarios"

    def compute_withholding(
        self,
        taxable_base,
        periodicity,
        date,
        monthly_income=None,
        days=None,
        with_subsidy=True,
    ):
        """Tax to withhold for one payment.

        ``taxable_base`` is the taxable amount of *this* payment, in the units
        of ``periodicity``. ``monthly_income`` is the monthly income used only
        to test the subsidy limit, which the decree states per month regardless
        of how often the worker is paid; for a fortnightly payslip the two
        numbers are different and the caller is what knows the monthly one.
        ``days`` is how many days the period covers, required whenever the
        periodicity is shorter than a month.

        Returns the tax caused, the subsidy that corresponds, how much of it
        could be applied, what is withheld, and what is left over.

        **The leftover is not money.** The decree is explicit: when the tax is
        smaller than the subsidy, the difference "no podrá aplicarse contra el
        impuesto que resulte a su cargo posteriormente, ni se entregará
        cantidad alguna". It is reported as ``subsidy_forgone`` so a payroll can
        show it, never as something to pay.
        """
        if not date:
            raise UserError(
                self.env._(
                    "Falta la fecha del pago. Sin ella no se puede saber qué "
                    "tarifa ni qué subsidio estaban vigentes."
                )
            )
        if taxable_base < 0 or (monthly_income is not None and monthly_income < 0):
            raise UserError(
                self.env._(
                    "La base gravable y el ingreso mensual no pueden ser negativos."
                )
            )
        if periodicity == "annual" and with_subsidy:
            raise UserError(
                self.env._(
                    "La tarifa anual corresponde al cálculo del impuesto del "
                    "ejercicio. Ahí el impuesto se disminuye con la suma de los "
                    "subsidios mensuales que le correspondieron al trabajador "
                    "durante el año, un dato que este método no conoce a partir "
                    "de un solo pago. Calcula el impuesto con with_subsidy=False "
                    "y réstale esa suma."
                )
            )

        tariff = self.env["l10n_mx.isr.tariff"].get_for_date(periodicity, date)
        tax = tariff.compute_tax(taxable_base)

        subsidy = 0.0
        if with_subsidy:
            if monthly_income is None:
                if periodicity != "monthly":
                    raise UserError(
                        self.env._(
                            "Falta el ingreso mensual. El límite del subsidio para "
                            "el empleo está fijado por mes, así que en un pago "
                            "%(periodicity)s no se puede deducir de la base del "
                            "propio pago.",
                            periodicity=periodicity,
                        )
                    )
                monthly_income = taxable_base
            if periodicity in SUB_MONTHLY and not days:
                raise UserError(
                    self.env._(
                        "Falta el número de días del periodo. El subsidio de un "
                        "pago %(periodicity)s se prorratea por los días que cubre, "
                        "y ese número depende del periodo concreto, no de su "
                        "nombre: una quincena puede ser de 15 o de 16 días.",
                        periodicity=periodicity,
                    )
                )
            parameters = self.env["l10n_mx.employment.subsidy"].get_for_date(date)
            subsidy = parameters.compute(monthly_income, date, days=days)

        # The subsidy is a credit against the tax and nothing else. Anything
        # above the tax is lost: it is neither paid nor carried forward.
        applied = float_round(min(subsidy, tax), precision_digits=2)
        withheld = float_round(tax - applied, precision_digits=2)
        forgone = float_round(subsidy - applied, precision_digits=2)
        return {
            "tax": tax,
            "subsidy": subsidy,
            "subsidy_applied": applied,
            "withheld": withheld,
            "subsidy_forgone": forgone,
        }
