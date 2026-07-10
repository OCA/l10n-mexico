from odoo.exceptions import ValidationError

from .common import WaybillTestCommon


class TestCFDIVehicle(WaybillTestCommon):
    def _vehicle_vals(self, **extra):
        vals = {
            "name": "Truck Test",
            "plate": "ABC123",
            "model": "2024",
            "vehicle_setup": self.vehicle.vehicle_setup.id,
            "gross_vehicle_weight": 3500.0,
            "permit_type": self.vehicle.permit_type.id,
            "permit_number": "PERM001",
            "insurance_company": self.partner.id,
            "insurance_number": "INS001",
        }
        vals.update(extra)
        return vals

    def test_vehicle_validate_success(self):
        self.vehicle.validate()

    def test_vehicle_validate_missing_plate(self):
        vehicle = self.env["l10n_mx_cfdi_waybill.vehicle"].new(
            self._vehicle_vals(plate=False)
        )
        with self.assertRaises(ValidationError):
            vehicle.validate()

    def test_vehicle_validate_missing_model(self):
        vehicle = self.env["l10n_mx_cfdi_waybill.vehicle"].new(
            self._vehicle_vals(model=False)
        )
        with self.assertRaises(ValidationError):
            vehicle.validate()

    def test_vehicle_validate_missing_setup(self):
        vehicle = self.env["l10n_mx_cfdi_waybill.vehicle"].new(
            self._vehicle_vals(vehicle_setup=False)
        )
        with self.assertRaises(ValidationError):
            vehicle.validate()

    def test_vehicle_validate_missing_permit_type(self):
        vehicle = self.env["l10n_mx_cfdi_waybill.vehicle"].new(
            self._vehicle_vals(permit_type=False)
        )
        with self.assertRaises(ValidationError):
            vehicle.validate()

    def test_vehicle_validate_missing_permit_number(self):
        vehicle = self.env["l10n_mx_cfdi_waybill.vehicle"].new(
            self._vehicle_vals(permit_number=False)
        )
        with self.assertRaises(ValidationError):
            vehicle.validate()

    def test_vehicle_validate_missing_insurance_company(self):
        vehicle = self.env["l10n_mx_cfdi_waybill.vehicle"].new(
            self._vehicle_vals(insurance_company=False)
        )
        with self.assertRaises(ValidationError):
            vehicle.validate()

    def test_vehicle_validate_missing_insurance_number(self):
        vehicle = self.env["l10n_mx_cfdi_waybill.vehicle"].new(
            self._vehicle_vals(insurance_number=False)
        )
        with self.assertRaises(ValidationError):
            vehicle.validate()
