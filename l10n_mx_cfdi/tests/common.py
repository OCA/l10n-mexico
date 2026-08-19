from base64 import b64encode

# Normalized create_cfdi() result used by tests that mock the PAC boundary.
ACTIVE_CFDI_RESPONSE = {
    "status": "published",
    "uuid": "11111111-1111-1111-1111-111111111111",
    "tracking_id": "tracking-123",
    "xml": (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
        b'Total="100.00" NoCertificado="CERT123" '
        b'Fecha="2024-01-01T12:00:00" Sello="' + b"A" * 100 + b'">'
        b"<cfdi:Complemento>"
        b"<tfd:TimbreFiscalDigital "
        b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
        b'UUID="11111111-1111-1111-1111-111111111111" '
        b'SelloSAT="sat-sign" NoCertificadoSAT="SATCERT" '
        b'RfcProvCertif="RFC123456" FechaTimbrado="2024-01-01T13:00:00"/>'
        b"</cfdi:Complemento></cfdi:Comprobante>"
    ),
    "pdf": None,
    "stamp_meta": {
        "Date": "2024-01-01T12:00:00",
        "CertNumber": "CERT123",
        "OriginalString": "original-string",
        "Total": "100.00",
        "Taxes": [{"Name": "IVA"}, {"Name": "ISR"}],
        "Complement": {
            "TaxStamp": {
                "Uuid": "11111111-1111-1111-1111-111111111111",
                "CfdiSign": "A" * 100,
                "SatSign": "sat-sign",
                "SatCertNumber": "SATCERT",
                "RfcProvCertif": "RFC123456",
                "Date": "2024-01-01T13:00:00",
            }
        },
    },
}


class CFDITestMixin:
    @classmethod
    def _create_cfdi_service(cls):
        return cls.env["l10n_mx_cfdi.cfdi_service"].create(
            {
                "name": "Test service",
                "provider": "finkok",
                "user": "test_user",
                "password": "test_password",
                "sandbox_mode": True,
            }
        )

    @classmethod
    def _create_cfdi_issuer(cls, service):
        return cls.env["l10n_mx_cfdi.issuer"].create(
            {
                "name": "Test Issuer",
                "vat": "RFC123456",
                "fiscal_name": "Issuer SA de CV",
                "logo_url": "https://example.com/logo.png",
                "tax_regime": cls.env.ref("l10n_mx_catalogs.c_regimen_fiscal_616").id,
                "certificate_file": b64encode(b"certificate"),
                "key_file": b64encode(b"key"),
                "key_password": "password",
                "service_id": service.id,
            }
        )

    @classmethod
    def _create_cfdi_partner(cls):
        return cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "vat": "TESTVAT123",
                "zip": "12345",
            }
        )

    @classmethod
    def _create_document(cls, **extra):
        vals = {
            "issuer_id": cls.issuer.id,
            "receiver_id": cls.partner.id,
            "type": "I",
            "serie": "A",
            "folio": "1",
        }
        vals.update(extra)
        return cls.env["l10n_mx_cfdi.document"].create(vals)
