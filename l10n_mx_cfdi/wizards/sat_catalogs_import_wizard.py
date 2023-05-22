import base64

import xlrd

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SatCatalogsImportWizard(models.TransientModel):
    _name = "l10n_mx_cfdi.sat_catalogs_import_wizard"
    _description = "Wizard to Import SAT Catalogs"

    catalog_type = fields.Selection(
        selection=[
            ("CFDI_4_0", _("CFDI 4.0")),
            ("WAYBILL_2_0", _("WAYBILL 2.0")),
        ],
        string="Catalog Type",
        required=True,
        default="CFDI_4_0",
    )

    catalog_file = fields.Binary(
        string="Catalog File",
        required=True,
        help="Select the file to import. The file must be in XLSX format.",
    )

    line_ids = fields.One2many(
        comodel_name="l10n_mx_cfdi.sat_catalogs_import_wizard_line",
        inverse_name="wizard_id",
        string="Lines",
    )

    @api.depends("catalog_file")
    def _compute_line_ids(self):
        pass

    def action_import(self):
        self.ensure_one()

        if not self.catalog_file:
            raise UserError(_("You must select a file to import."))

        catalog_file_data = base64.b64decode(self.catalog_file)
        book = xlrd.open_workbook(file_contents=catalog_file_data)
        if not book:
            raise UserError(_("The selected file is not a valid XLS file."))

        for line in self.line_ids:
            for sheet in book.sheets():
                if sheet.name == line.sheet_title:
                    line._import_sheet(line.target_model)

    def action_reset_mappings(self):
        self.ensure_one()

        if not self.catalog_file:
            raise UserError(_("You must select a file to import."))

        catalog_file_data = base64.b64decode(self.catalog_file)
        book = xlrd.open_workbook(file_contents=catalog_file_data)
        if not book:
            raise UserError(_("The selected file is not a valid XLS file."))

        default_mappings = None
        if self.catalog_type == "CFDI_4_0":
            default_mappings = self._get_default_cfdi_4_0_mappings(book)

        if default_mappings:
            self.line_ids.unlink()
            for page, model in default_mappings.items():
                self.line_ids.create(
                    {
                        "wizard_id": self.id,
                        "sheet_title": page,
                        "target_model": model,
                    }
                )

    def _get_default_cfdi_4_0_mappings(self, book):
        self.ensure_one()

        # possible models to map to
        target_model_selection = self.line_ids._fields["target_model"].selection
        target_models = [
            self.env[model_name] for model_name, _ in target_model_selection
        ]

        results = {}
        # iterate over all sheets in the workbook
        for sheet in book.sheets():
            sheet_name = sheet.name.lower()
            # iterate over all possible models to map to
            for target_model in target_models:
                catalog_name = target_model._l10n_mx_catalog_name.lower()
                if catalog_name in sheet_name:
                    results[sheet.name] = target_model._name

        return results


class SatCatalogsImportWizardLine(models.TransientModel):
    _name = "l10n_mx_cfdi.sat_catalogs_import_wizard_line"
    _description = "Wizard to Import SAT Catalogs"

    wizard_id = fields.Many2one(
        comodel_name="l10n_mx_cfdi.sat_catalogs_import_wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )

    sheet_title = fields.Char(
        string="Page Title",
        required=True,
    )

    target_model = fields.Selection(
        selection=[
            ("l10n_mx_cfdi.cfdi_type", _("Type")),
            ("l10n_mx_cfdi.cfdi_zip_codes", _("Zip Codes")),
            ("l10n_mx_cfdi.cfdi_municipality_code", _("Municipality")),
            ("l10n_mx_cfdi.cfdi_locality_code", _("Locality")),
            ("l10n_mx_cfdi.cfdi_product_and_service_code", _("Product or Service")),
            ("l10n_mx_cfdi.cfdi_payment_policy", _("Payment Policy")),
            ("l10n_mx_cfdi.cfdi_payment_way", _("Payment Way")),
            ("res.country.state", _("State")),
            ("res.country", _("Country")),
        ],
        string="Target Model",
        required=True,
    )

    def _import_sheet(self, sheet):
        model = self.env[self.target_model]
        col_name_mappings = model._l10n_mx_catalog_col_mapping
        col_names = set(col_name_mappings.keys())
        field_mappings = dict()

        # iterate over all rows in the sheet
        headers_row_found = False
        for row_idx in range(1, sheet.nrows):
            row_data = sheet.row(row_idx)

            # the first row is the headers row
            if not headers_row_found:
                # allow comparison by convert values to strings
                row_data = [str(cell.value) for cell in row_data]
                if col_names <= set(row_data):
                    headers_row_found = True

                    # save col index for each field
                    for row_name, field_name in col_name_mappings.items():
                        row_idx = row_data.index(row_name)
                        field_mappings[row_idx] = field_name

                        # headers row and other pre-header rows will be ignored
                continue

            record_dict = self._map_row_to_record_dict(field_mappings, row_data)

            # ignore rows without code
            if not record_dict['code']:
                continue

            # create or update the record
            record = self._find_existent_record(model, record_dict)
            if record:
                record.write(record_dict)
            else:
                model.create(record_dict)

    def _find_existent_record(self, model, record_dict):
        """
        Find a record in the database that matches the given record_dict

        Special resolution is applied for models inherited from other
        modules, such as res.country.
        """

        record = model.search([("code", "=", record_dict["code"])])
        return record

    def _map_row_to_record_dict(self, field_mappings, row_data):
        """
        Map a row of data from the xls catalog to a dictionary of field values

        Patches are applied to normalize the data to the expected format.

        """
        record_dict = {}
        for idx, value in enumerate(row_data):
            if idx in field_mappings:
                field_name = field_mappings[idx]
                record_dict[field_name] = value.value

        if self.target_model == 'l10n_mx_cfdi.cfdi_payment_way':
            # payment ways are 2 digits
            record_dict['code'] = '%02d' % record_dict['code']

        return record_dict
