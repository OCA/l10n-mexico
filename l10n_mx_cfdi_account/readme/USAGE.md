Use this module after the PAC connection, issuers, and series are configured in
``l10n_mx_cfdi`` (see that module's Configuration).

## Customers

1. In the Invoicing app, go to Customers > Customers.
2. Create or open a customer with the correct VAT (RFC) and fiscal name.
3. On the **CFDI** tab, set:

   - Fiscal regime
   - Default CFDI usage
   - Default payment method
   - Default payment form

## Products

1. Go to Customers > Products (or open a product from Inventory).
2. Open an existing product or create a new one and enter the general
   information.
3. On the **CFDI** tab, set the SAT product code and unit of measure.

## Invoices

1. Go to Customers > Invoices and create a new record.
2. Select the customer. The fiscal data on the partner CFDI tab is required for
   stamping.
3. Add products that have a SAT product code.
4. Open the **CFDI** tab and set the payment method and payment form.
5. Confirm the invoice; it is stamped with the Mexican authority through the
   configured PAC.
6. Use Send to deliver the invoice to the customer.

### Import CFDI

- Attach the vendor bill XML file in the chatter.
- Click the **Load from file** button.

## Payments

If the invoice payment method is PPD, the payment is included in the CFDI lines
when you register a payment.
