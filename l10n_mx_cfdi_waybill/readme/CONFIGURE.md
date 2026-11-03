Configure vehicles, transporters, and CFDI issuers before creating waybills from
inventory transfers.

To transport hazardous materials (Carta Porte 3.1):

- On each product, set **Material peligroso CFDI** to the value of the
  "Material peligroso" column of its SAT product key (``c_ClaveProdServCP``):

  - **No** (``0``): the good is sent with ``MaterialPeligroso="No"``.
  - **Sí** (``1``): the hazardous material key, the packaging code and the
    packaging description are required and sent with ``MaterialPeligroso="Sí"``.
  - **Opcional** (``0,1``): if the hazardous material key is filled in, the good
    is sent as "Sí" with the key and packaging; otherwise it is sent as "No".

- On the vehicle, fill in the environmental insurer and policy number. They are
  required when the waybill carries at least one good sent as "Sí" and are sent
  as ``AseguraMedAmbiente`` and ``PolizaMedAmbiente``.
