# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging
from datetime import datetime as dt

from odoo import api, fields, models
from odoo.exceptions import AccessError

from ..services.sat_metadata import (
    SAT_STATUS_VALID,
    normalize_sat_status,
)

_logger = logging.getLogger(__name__)

CFDI_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class L10nMxSatDocument(models.Model):
    _name = "l10n_mx_sat.document"
    _description = "SAT Document"
    _order = "issue_date desc, uuid"
    _rec_name = "display_name"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        readonly=True,
        index=True,
    )
    uuid = fields.Char(string="UUID", required=True, readonly=True, index=True)
    document_kind = fields.Selection(
        selection=[
            ("cfdi", "CFDI"),
            ("retention", "Retention"),
        ],
        string="Document kind",
        readonly=True,
        required=True,
        index=True,
    )
    direction = fields.Selection(
        selection=[
            ("issued", "Issued"),
            ("received", "Received"),
        ],
        required=True,
        readonly=True,
        index=True,
    )
    sat_status = fields.Selection(
        selection=[
            ("valid", "Valid"),
            ("cancelled", "Cancelled"),
            ("in_progress", "In progress"),
        ],
        string="SAT status",
        index=True,
        readonly=True,
    )
    voucher_type = fields.Char(string="Voucher type", readonly=True, index=True)
    issuer_rfc = fields.Char(string="Issuer RFC", readonly=True, index=True)
    issuer_name = fields.Char(string="Issuer name", readonly=True)
    receiver_rfc = fields.Char(string="Receiver RFC", readonly=True, index=True)
    receiver_name = fields.Char(string="Receiver name", readonly=True)
    issue_date = fields.Datetime(string="Issue date", readonly=True, index=True)
    stamp_date = fields.Datetime(string="Stamp date", readonly=True)
    cancellation_date = fields.Datetime(string="Cancellation date", readonly=True)
    total = fields.Float(digits=(16, 6), readonly=True)
    currency_code = fields.Char(string="Currency", readonly=True)
    series = fields.Char(readonly=True)
    folio_number = fields.Char(string="Folio", readonly=True)
    has_xml = fields.Boolean(string="Has XML", default=False, readonly=True, index=True)
    download_request_id = fields.Many2one(
        comodel_name="l10n_mx_sat.download.request",
        string="SAT request",
        readonly=True,
        ondelete="set null",
    )
    attachment_id = fields.Many2one(
        comodel_name="ir.attachment",
        string="XML",
        readonly=True,
        ondelete="set null",
    )
    display_name = fields.Char(
        compute="_compute_display_name", store=True, readonly=True
    )

    _uuid_company_kind_direction_uniq = models.Constraint(
        "UNIQUE(uuid, company_id, document_kind, direction)",
        "A SAT document with this UUID already exists for this company.",
    )

    @api.depends("uuid", "document_kind", "direction", "company_id.vat")
    def _compute_display_name(self):
        fields_info = self.fields_get(["document_kind", "direction"])
        kind_labels = dict(fields_info["document_kind"]["selection"])
        direction_labels = dict(fields_info["direction"]["selection"])
        for doc in self:
            parts = [doc.uuid or "?"]
            if doc.document_kind:
                parts.append(kind_labels.get(doc.document_kind, doc.document_kind))
            if doc.direction:
                parts.append(direction_labels.get(doc.direction, doc.direction))
            doc.display_name = " / ".join(parts)

    @api.model
    def _sat_document_readonly_message(self):
        return self.env._(
            "SAT documents are read-only and can only be updated "
            "through SAT download requests."
        )

    @api.model
    def _check_not_manual_update(self):
        message = self._sat_document_readonly_message()
        # Block every non-internal write, even when ACL or Settings grants access.
        raise AccessError(message)

    @api.model_create_multi
    def _sat_create(self, vals_list):
        """Create SAT documents from trusted internal sync code only."""
        return super(L10nMxSatDocument, self.sudo()).create(vals_list)

    def _sat_write(self, vals):
        """Update SAT documents from trusted internal sync code only."""
        return super(L10nMxSatDocument, self.sudo()).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        self._check_not_manual_update()
        return super().create(vals_list)

    def write(self, vals):
        self._check_not_manual_update()
        return super().write(vals)

    def unlink(self):
        self._check_not_manual_update()
        return super().unlink()

    def get_formview_action(self, access_uid=None):
        """Always open SAT documents in readonly mode (list, menu, x2many)."""
        action = super().get_formview_action(access_uid=access_uid)
        action["flags"] = dict(action.get("flags") or {}, mode="readonly")
        ctx = dict(action.get("context") or {})
        ctx.update(create=False, edit=False, delete=False)
        action["context"] = ctx
        return action

    @api.model
    def _find_document(self, uuid, company, document_kind, direction):
        return self.search(
            [
                ("uuid", "=", uuid),
                ("company_id", "=", company.id),
                ("document_kind", "=", document_kind),
                ("direction", "=", direction),
            ],
            limit=1,
        )

    @api.model
    def _upsert_from_metadata_row(self, row, company, request):
        """Create or update a document from SAT metadata row."""
        uuid = (row.get("uuid") or "").upper()
        if not uuid:
            return self.browse()

        document = self._find_document(
            uuid, company, request.document_kind, request.direction
        )
        write_vals = {"download_request_id": request.id}
        field_map = (
            ("sat_status", "sat_status"),
            ("issuer_rfc", "issuer_rfc"),
            ("issuer_name", "issuer_name"),
            ("receiver_rfc", "receiver_rfc"),
            ("receiver_name", "receiver_name"),
            ("voucher_type", "voucher_type"),
        )
        for target, source in field_map:
            value = row.get(source)
            if value:
                write_vals[target] = value
            elif document:
                write_vals[target] = document[target]

        if row.get("total"):
            try:
                write_vals["total"] = float(row["total"])
            except (TypeError, ValueError) as err:
                _logger.debug("Could not parse metadata total: %s", err)
        for date_field, row_key in (
            ("issue_date", "issue_date"),
            ("stamp_date", "stamp_date"),
            ("cancellation_date", "cancellation_date"),
        ):
            parsed = self._parse_sat_datetime(row.get(row_key))
            if parsed:
                write_vals[date_field] = parsed

        if document:
            document._sat_write({k: v for k, v in write_vals.items() if v is not None})
            return document

        document = self._sat_create(
            [
                {
                    "company_id": company.id,
                    "uuid": uuid,
                    "document_kind": request.document_kind,
                    "direction": request.direction,
                    **write_vals,
                }
            ]
        )
        return self.browse(document.id)

    @api.model
    def _upsert_from_xml(self, tree, xml_bytes, company, request):
        """Create or update a document from a CFDI/retencion XML."""
        uuid = self._extract_uuid(tree)
        if not uuid:
            _logger.warning("XML without UUID, skipping")
            return self.browse()

        if not self._validate_xml_company(tree, company, request):
            _logger.warning(
                "Skipping XML for company %(company)s: UUID=%(uuid)s, "
                "document_kind=%(kind)s, direction=%(direction)s",
                {
                    "company": company.display_name,
                    "uuid": uuid,
                    "kind": request.document_kind,
                    "direction": request.direction,
                },
            )
            return self.browse()

        vals = self._parse_xml_values(tree, request.document_kind)
        document = self._find_document(
            uuid, company, request.document_kind, request.direction
        )
        vals["download_request_id"] = request.id
        vals["has_xml"] = True

        if document:
            document._sat_write({k: v for k, v in vals.items() if v is not None})
        else:
            sat_document = self._sat_create(
                [
                    {
                        "company_id": company.id,
                        "uuid": uuid,
                        "document_kind": request.document_kind,
                        "direction": request.direction,
                        **vals,
                    }
                ]
            )
            document = self.browse(sat_document.id)

        attachment = document.attachment_id
        attachment_vals = {
            "name": f"{uuid}.xml",
            "raw": xml_bytes,
            "res_model": self._name,
            "res_id": document.id,
            "mimetype": "application/xml",
            "company_id": company.id,
        }
        if attachment:
            attachment.write({"raw": xml_bytes})
        else:
            attachment = self.env["ir.attachment"].create(attachment_vals)
            document._sat_write({"attachment_id": attachment.id})
        return document

    @api.model
    def _extract_uuid(self, tree):
        tfd_nodes = tree.xpath("//*[local-name()='TimbreFiscalDigital']")
        if tfd_nodes:
            uuid = tfd_nodes[0].get("UUID")
            if uuid:
                return uuid.upper()
        folio_number = tree.get("FolioFiscal") or tree.get("UUID")
        return folio_number.upper() if folio_number else False

    @api.model
    def _find_by_local_name(self, tree, local_name):
        """Return all nodes matching a local XML name, ignoring namespaces."""
        return tree.xpath(f"//*[local-name()='{local_name}']")

    @api.model
    def _first_attr(self, node, *names):
        """Return the first non-empty attribute value from the given names."""
        if node is None:
            return False
        for name in names:
            value = node.get(name)
            if value and str(value).strip():
                return str(value).strip()
        return False

    @api.model
    def _get_company_rfc(self, company):
        """Resolve company RFC from VAT or FIEL credentials."""
        rfc = (company.vat or "").strip().upper()
        if rfc:
            return rfc
        if company.l10n_mx_sat_has_credentials():
            try:
                return company.l10n_mx_sat_get_rfc()
            except Exception:
                return False
        return False

    @api.model
    def _get_retention_emisor_rfc(self, tree):
        emisor_nodes = self._find_by_local_name(tree, "Emisor")
        if not emisor_nodes:
            return False
        rfc = self._first_attr(
            emisor_nodes[0], "Rfc", "RfcEmisor", "RFCEmisor", "rfcEmisor"
        )
        return rfc.upper() if rfc else False

    @api.model
    def _get_retention_emisor_name(self, tree):
        emisor_nodes = self._find_by_local_name(tree, "Emisor")
        if not emisor_nodes:
            return False
        return self._first_attr(
            emisor_nodes[0], "Nombre", "NomDenRazSocE", "NomDenRazSocEmisor"
        )

    @api.model
    def _get_retention_receptor_rfc(self, tree):
        receptor_nodes = self._find_by_local_name(tree, "Receptor")
        if not receptor_nodes:
            return False
        receptor = receptor_nodes[0]
        rfc = self._first_attr(
            receptor, "Rfc", "RfcReceptor", "RFCRecep", "RfcR", "rfcReceptor"
        )
        if rfc:
            return rfc.upper()
        nacional_nodes = self._find_by_local_name(receptor, "Nacional")
        if nacional_nodes:
            rfc = self._first_attr(
                nacional_nodes[0],
                "RfcR",
                "RFCRecep",
                "RfcReceptor",
                "Rfc",
                "rfcReceptor",
            )
            if rfc:
                return rfc.upper()
        extranjero_nodes = self._find_by_local_name(receptor, "Extranjero")
        if extranjero_nodes:
            rfc = self._first_attr(
                extranjero_nodes[0],
                "NumRegIdTrib",
                "NumRegIdTribReceptor",
                "NumRegIdTribR",
            )
            if rfc:
                return rfc.upper()
        return False

    @api.model
    def _get_retention_receptor_name(self, tree):
        receptor_nodes = self._find_by_local_name(tree, "Receptor")
        if not receptor_nodes:
            return False
        receptor = receptor_nodes[0]
        name = self._first_attr(
            receptor, "Nombre", "NomDenRazSocR", "NomDenRazSocReceptor"
        )
        if name:
            return name
        nacional_nodes = self._find_by_local_name(receptor, "Nacional")
        if nacional_nodes:
            name = self._first_attr(
                nacional_nodes[0],
                "NomDenRazSocR",
                "NomDenRazSocReceptor",
                "Nombre",
            )
            if name:
                return name
        extranjero_nodes = self._find_by_local_name(receptor, "Extranjero")
        if extranjero_nodes:
            return self._first_attr(
                extranjero_nodes[0],
                "NomDenRazSocR",
                "NomDenRazSocReceptor",
                "Nombre",
            )
        return False

    @api.model
    def _get_retention_total(self, tree):
        totales_nodes = self._find_by_local_name(tree, "Totales")
        if totales_nodes:
            total = self._first_attr(
                totales_nodes[0],
                "MontoTotOperacion",
                "montoTotOperacion",
                "MontoTotRet",
                "montoTotRet",
                "Total",
            )
            if total:
                try:
                    return float(total)
                except (TypeError, ValueError) as err:
                    _logger.debug("Could not parse retention total: %s", err)
        for attr in ("MontoTotOperacion", "montoTotOperacion", "MontoTotRet", "Total"):
            value = tree.get(attr)
            if value:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return 0.0

    @api.model
    def _validate_xml_company(self, tree, company, request):
        company_rfc = self._get_company_rfc(company)
        if request.document_kind == "cfdi":
            if request.direction == "received":
                receptor = tree.find("{*}Receptor")
                if receptor is None:
                    return False
                rfc = (receptor.get("Rfc") or "").upper()
                return rfc == company_rfc
            emisor = tree.find("{*}Emisor")
            if emisor is None:
                return False
            rfc = (emisor.get("Rfc") or "").upper()
            return rfc == company_rfc
        if not company_rfc:
            return True
        if request.direction == "received":
            rfc = self._get_retention_receptor_rfc(tree)
        else:
            rfc = self._get_retention_emisor_rfc(tree)
        return bool(rfc) and rfc == company_rfc

    @api.model
    def _parse_xml_values(self, tree, document_kind):
        vals = {}
        if document_kind == "cfdi":
            emisor = tree.find("{*}Emisor")
            receptor = tree.find("{*}Receptor")
            if emisor is not None:
                vals["issuer_rfc"] = emisor.get("Rfc")
                vals["issuer_name"] = emisor.get("Nombre")
            if receptor is not None:
                vals["receiver_rfc"] = receptor.get("Rfc")
                vals["receiver_name"] = receptor.get("Nombre")
            vals["voucher_type"] = tree.get("TipoDeComprobante")
            vals["currency_code"] = tree.get("Moneda")
            vals["series"] = tree.get("Serie")
            vals["folio_number"] = tree.get("Folio")
            try:
                vals["total"] = float(tree.get("Total") or 0)
            except (TypeError, ValueError) as err:
                _logger.debug("Could not parse CFDI total: %s", err)
            vals["issue_date"] = self._parse_sat_datetime(tree.get("Fecha"))
            tfd = tree.xpath("//*[local-name()='TimbreFiscalDigital']")
            if tfd:
                vals["stamp_date"] = self._parse_sat_datetime(
                    tfd[0].get("FechaTimbrado")
                )
        else:
            vals["issuer_rfc"] = self._get_retention_emisor_rfc(tree)
            vals["issuer_name"] = self._get_retention_emisor_name(tree)
            vals["receiver_rfc"] = self._get_retention_receptor_rfc(tree)
            vals["receiver_name"] = self._get_retention_receptor_name(tree)
            vals["issue_date"] = self._parse_sat_datetime(
                tree.get("FechaExp") or tree.get("Fecha")
            )
            vals["total"] = self._get_retention_total(tree)
            tfd = tree.xpath("//*[local-name()='TimbreFiscalDigital']")
            if tfd:
                vals["stamp_date"] = self._parse_sat_datetime(
                    tfd[0].get("FechaTimbrado")
                )
        if not vals.get("sat_status"):
            vals["sat_status"] = SAT_STATUS_VALID
        return vals

    @api.model
    def _parse_sat_datetime(self, value):
        if not value:
            return False
        value = str(value).strip()
        for fmt, size in (
            (CFDI_DATE_FORMAT, 19),
            ("%Y-%m-%d %H:%M:%S", 19),
            ("%Y-%m-%d", 10),
        ):
            try:
                return dt.strptime(value[:size], fmt)
            except ValueError:
                continue
        return False

    def action_download_xml(self):
        self.ensure_one()
        if not self.attachment_id:
            return False
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self.attachment_id.id}?download=true",
            "target": "self",
        }

    @api.model
    def _update_status_from_validate(self, document, validate_result):
        estado = normalize_sat_status(validate_result.get("estado"))
        if estado:
            document._sat_write({"sat_status": estado})
