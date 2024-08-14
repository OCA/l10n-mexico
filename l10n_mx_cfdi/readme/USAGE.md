### Service Configuration

Right now, this module works only with Facturama as the PAC,
so anyone who want to make use of it needs to have an account configured in
[Facturama](https://facturama.mx/)

1. Go to Invoicing > Configuration > CFDI > Service Configuration
2. Click **"New"** to add your _Facturama_ account
   1. "_Name"_ -> Name of the service. Name it "Facturama"
   2. _"User"_ -> Your facturama account Username
   3. _"Password"_ -> Your facturama account password
   4. _"Sandbox mode"_ -> If you don't want to send your invoices to SAT and just test

### Issuers
This module lets the user choose between different profiles that will emmit the invoice

1. Go to Invoicing > Configuration > CFDI > Issuers
2. Click **"New"** to add an Issuer
   1. _"Name"_ -> Name of the issuer. This is just to locate it
   2. _"Fiscal Name"_ -> The real name of the issuer (natural or legal)
   3. _"Service"_ -> The service generated (facturama for now)
3. Click **"Register"**
4. If the issuer is registered correctly, the checkbox will appear checked and the error message will disappear
