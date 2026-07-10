from unittest.mock import patch

import requests

from odoo.exceptions import UserError
from odoo.tests.common import mute_logger

from odoo.addons.base.tests.common import BaseCommon


class TestBaseGeocoderWaybill(BaseCommon):
    def test_geo_query_route_wrong_provider(self):
        geocoder = self.env["base.geocoder"]
        partner = self.env["res.partner"].create({"name": "Partner"})
        with patch.object(
            type(geocoder),
            "_get_provider",
            return_value=type("P", (), {"tech_name": "google"})(),
        ):
            with self.assertRaises(UserError):
                geocoder.geo_query_route(partner, partner)

    @patch("odoo.addons.l10n_mx_cfdi_waybill.models.base_geocoder.requests.get")
    def test_geo_query_route_openstreetmap(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "code": "Ok",
            "routes": [{"distance": 1000, "duration": 3600}],
        }
        geocoder = self.env["base.geocoder"]
        origin = self.env["res.partner"].create(
            {"name": "Origin", "partner_latitude": 19.0, "partner_longitude": -99.0}
        )
        dest = self.env["res.partner"].create(
            {"name": "Dest", "partner_latitude": 20.0, "partner_longitude": -98.0}
        )
        with patch.object(
            type(geocoder),
            "_get_provider",
            return_value=type("P", (), {"tech_name": "openstreetmap"})(),
        ):
            route = geocoder.geo_query_route(origin, dest)
        self.assertEqual(route["distance"], 1000)
        self.assertEqual(route["duration"], 3600)

    @patch("odoo.addons.l10n_mx_cfdi_waybill.models.base_geocoder.requests.get")
    def test_geo_query_route_not_ok(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"code": "NoRoute"}
        geocoder = self.env["base.geocoder"]
        origin = self.env["res.partner"].create(
            {"name": "Origin", "partner_latitude": 19.0, "partner_longitude": -99.0}
        )
        dest = self.env["res.partner"].create(
            {"name": "Dest", "partner_latitude": 20.0, "partner_longitude": -98.0}
        )
        with patch.object(
            type(geocoder),
            "_get_provider",
            return_value=type("P", (), {"tech_name": "openstreetmap"})(),
        ):
            route = geocoder.geo_query_route(origin, dest)
        self.assertFalse(route)

    @mute_logger("odoo.addons.l10n_mx_cfdi_waybill.models.base_geocoder")
    @patch("odoo.addons.l10n_mx_cfdi_waybill.models.base_geocoder.requests.get")
    def test_call_openstreetmap_non_200(self, mock_get):
        mock_get.return_value.status_code = 500
        mock_get.return_value.json.return_value = {"code": "Error"}
        geocoder = self.env["base.geocoder"]
        result = geocoder._call_openstreetmap_route_api((19.0, -99.0), (20.0, -98.0))
        self.assertEqual(result["code"], "Error")

    @patch("odoo.addons.l10n_mx_cfdi_waybill.models.base_geocoder.requests.get")
    def test_call_openstreetmap_request_error(self, mock_get):
        mock_get.side_effect = requests.RequestException("network error")
        geocoder = self.env["base.geocoder"]
        with self.assertRaises(UserError):
            geocoder._call_openstreetmap_route_api((19.0, -99.0), (20.0, -98.0))
