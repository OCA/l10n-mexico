Follow these stages to connect Odoo to your PAC and prepare issuers for
stamping. For provider pricing, signup links, and stamp vs issue notes, see
Installation.

## 1. Create PAC Settings

1. Go to **CFDI > PAC Settings** and create a record (or open an existing one).
2. Set a name and choose the **Provider** (Finkok, Diverza, Prodigia, Comercio
   Digital, SW Sapien, MYSuite, Facturama, or Cefidia).
3. Assign the companies that will use this PAC connection (multi-company).

## 2. Enter credentials

Fill in the **Credentials** group fields that apply to your provider
(Settings users / system group):

| Provider | Typical fields |
|----------|----------------|
| Finkok | User, Password |
| Diverza | Password or PAC Token, PAC RFC, PAC Client ID |
| Prodigia | User, Password, PAC Contract |
| Comercio Digital | User, Password |
| SW Sapien | PAC Token, or User and Password |
| MYSuite | User, PAC Requestor, PAC Country (default MX) |
| Facturama | User, Password |
| Cefidia | PAC Token (``cfd_...`` secret token with ``cefidia:write``) |

Credential names and requirements can vary by PAC contract; confirm with the
provider documentation if a field is unclear.

## 3. Select environment

Enable **Sandbox Mode** for the PAC test environment. Leave it disabled for
production.

Cefidia has no sandbox flag: the environment is decided by the certificate in
the XML. To test, add one of the SAT test RFCs in Cefidia (it installs the SAT
test certificate) and use that RFC and its CSD on the issuer.

## 4. Configure CFDI issuer(s) and register the CSD

1. Go to **CFDI > Issuers** and create an issuer linked to the PAC Settings
   record.
2. Set RFC, fiscal name, ZIP, and tax regime.
3. Upload the CSD certificate, private key, and key password.
4. Click **Registrar** to validate the CSD locally (used for ``stamp()`` and
   for cancel where applicable).

### Facturama Multiemisor

For Facturama, **Registrar** also uploads the issuer CSD to the PAC. That
upload is required before ``issue()``. Re-register issuers after switching to
the satcfdi Facturama adapter so the Multiemisor CSD is uploaded again.

### Cefidia

Cefidia needs no registration step: the issuer is registered as soon as its
CSD certificate, private key and key password are set, and **Registrar** is
hidden. Stamping signs locally with the issuer CSD and sends the sealed XML to
Cefidia unchanged.

Cefidia's API does not accept CSD uploads, and cancellation uses the CSD
stored on Cefidia, so in the Cefidia account:

1. Add the issuer RFC as a taxpayer.
2. Upload its CSD on the taxpayer's Cefidia web page.

## 5. Configure series and folios

Go to **CFDI > Series** and define the series prefix and next folio when your
company uses controlled series/folios.

## 6. Finkok cancel (company FIEL)

For cancellation with PACs that require a signer (for example Finkok), install
``l10n_mx_sat`` and configure the company FIEL.

## 7. Validate the connection

Confirm that the issuer shows as registered, then stamp a test CFDI in sandbox
before switching to production. Prefer PACs that implement ``issue()`` when
possible; otherwise the module signs locally with the issuer CSD and calls
``stamp()``.
