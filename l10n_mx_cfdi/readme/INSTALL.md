This module works with any PAC supported by the
[satcfdi](https://github.com/SAT-CFDI/python-satcfdi) library:

* Finkok
* Diverza
* Prodigia
* Comercio Digital
* SW Sapien
* MYSuite
* Facturama

Install the Python dependency:

```bash
pip install "satcfdi>=26.7.3"
```

## PAC comparison

Indicative public list prices as of about 2026-07 (MXN). Amounts and packages
change without notice — always confirm with the vendor before contracting. OCA
and the module authors have no commercial relationship with these PACs; logos
are property of their respective owners and are used for identification only.

### Providers

![Finkok](../static/description/pac_logos/finkok.png)

**Finkok** — OnDemand: pay monthly for stamps issued. Public page states a
minimum of about 500 stamps/month (not accumulable); unit rates via sales
(historically cited about 150 MXN + IVA/month for the minimum block, then about
0.30 MXN + IVA per stamp — exact MXN rates were not listed on the public
OnDemand page at verification time).

- Contract / info: https://finkok.com/ · https://finkok.com/ondemand.html
- Module notes: username/password; supports ``issue()``; cancel requires a
  signer (company FIEL via ``l10n_mx_sat``).

![Diverza](../static/description/pac_logos/diverza.svg)

**Diverza (Timbre Fiscal)** — Pyme about 999 MXN + IVA/year (550 CFDIs);
Empresarial about 1,599 MXN + IVA/year (1,100 CFDIs). Larger plans via sales.

- Contract / info: https://portaldvz20.diverza.com/cfdi/timbre-fiscal/ ·
  https://www.diverza.com/
- Module notes: PAC RFC, client id, and token; supports ``issue()``.

![Prodigia](../static/description/pac_logos/prodigia.png)

**Prodigia (PADE)** — No public list prices; packages by volume / contact sales.
Stamps without expiry (per vendor marketing).

- Contract / info: https://www.prodigia.com.mx/soluciones/timbrado ·
  https://facturacion.pade.mx/
- Module notes: user/password/contrato; local seal + ``stamp()`` only
  (``supports_issue=False``); cancel not exposed in satcfdi.

![Comercio Digital](../static/description/pac_logos/comerciodigital.png)

**Comercio Digital** — Example stamp packs (+ IVA), 2-year validity: 200=400;
500=850; 1,000=1,400; 5,000=4,500; 10,000=7,800; 50,000=30,000;
100,000=45,000 MXN.

- Contract / info: https://www.comercio-digital.mx/comprar.html
- Module notes: user/password; local seal + ``stamp()`` only; cancel not
  exposed in satcfdi.

![SW Sapien](../static/description/pac_logos/swsapien.png)

**SW Sapien** — Odoo-oriented stamp packs (public store, MXN; confirm IVA):
1,200=2,266; 5,000=5,530; 10,000=8,230; 20,000=9,930; 30,000=11,830;
60,000=18,130; 100,000=23,730. No expiry (per vendor).

- Contract / info: https://tienda.sw.com.mx/shop/category/timbres-1 ·
  https://sw.com.mx/ · https://info.sw.com.mx/sw-smarter-odoo
- Module notes: token or user/password; supports ``issue()``.

![MYSuite](../static/description/pac_logos/mysuite.png)

**MYSuite** — Portal folio packs (WEB / PLUS / PREMIUM) for web billing; WS/API
pricing is typically quote-based (confirm with sales).

- Buy / info: https://comprar.mysuitemex.com/ ·
  https://www.mysuitemex.com/ · https://www.portal.mysuitemex.com/
- Module notes: requestor + user; local seal + ``stamp()`` only; cancel not
  exposed in satcfdi.

![Facturama](../static/description/pac_logos/facturama.png)

**Facturama** — API module about 1,650 MXN/year (incl. IVA), includes API Web +
Multiemisor and 100 folios; additional API folios about 0.50 / 0.45 / 0.40 MXN
(incl. IVA) by volume bands.

- Contract / info: https://facturama.mx/planes-facturacion ·
  https://facturama.mx/api-facturacion-electronica
- Module notes: username/password; Multiemisor path used by this module —
  **Registrar** uploads the issuer CSD to the PAC before ``issue()``;
  supports ``issue()``.

### Module integration (stamp vs issue)

| PAC | Path | Cancel in satcfdi | Credentials (summary) |
|-----|------|-------------------|------------------------|
| Finkok | ``issue()`` (or stamp) | Yes (signer required) | user / password |
| Diverza | ``issue()`` | Yes | PAC RFC, client id, token |
| Prodigia | local seal + ``stamp()`` | No | user / password / contrato |
| Comercio Digital | local seal + ``stamp()`` | No | user / password |
| SW Sapien | ``issue()`` | Yes | token or user / password |
| MYSuite | local seal + ``stamp()`` | No | requestor + user |
| Facturama | ``issue()`` (Multiemisor) | Yes | user / password; CSD upload on Registrar |

Prefer PACs that implement ``issue()`` when possible. Otherwise the module
signs locally with the issuer CSD and calls ``stamp()``.

After installing, follow Configuration to create **CFDI > PAC Settings**,
enter credentials, register issuer CSDs with **Registrar**, and (when needed)
configure series and company FIEL for Finkok cancel.

**Breaking migration from legacy Facturama API**

* Existing documents that only store a Facturama `tracking_id` without the
  stamped XML cannot be cancelled or recovered through satcfdi. Cancel them
  at the SAT / previous PAC, or attach the CFDI XML on the document first.
* Re-register issuers after switching to the satcfdi Facturama adapter so the
  Multiemisor CSD is uploaded again.
* Prodigia, Comercio Digital, and MYSuite do not expose cancel in satcfdi;
  the Cancel button stays hidden for those providers.
* Prefer PACs that implement `issue()` when possible; otherwise the module
  signs locally with the issuer CSD and calls `stamp()`.
