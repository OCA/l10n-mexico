import logging

import requests

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class GeoCoder(models.AbstractModel):
    _inherit = "base.geocoder"

    def geo_query_route(self, orig, dest):
        """Computes the route between two addresses."""
        provider = self._get_provider().tech_name
        if provider != "openstreetmap":
            raise UserError(
                self.env._("Route computation is only available with Openstreetmap.")
            )

        orig_coords = (orig.partner_latitude, orig.partner_longitude)
        dest_coords = (dest.partner_latitude, dest.partner_longitude)

        res = self._call_openstreetmap_route_api(orig_coords, dest_coords)
        if res and res["code"] == "Ok":
            return {
                "distance": res["routes"][0]["distance"],
                "duration": res["routes"][0]["duration"],
            }

    def _call_openstreetmap_route_api(self, orig, dest, include_steps=False):
        url = "https://routing.openstreetmap.de/routed-car/route/v1/driving/"
        url += f"{orig[1]:.14f},{orig[0]:.14f};{dest[1]:.14f},{dest[0]:.14f}"

        try:
            headers = {"User-Agent": "Odoo (http://www.odoo.com/contactus)"}
            response = requests.get(
                url,
                headers=headers,
                params={"steps": str(include_steps).lower()},
                timeout=30,
            )
            _logger.info("openstreetmap nominatim service called")
            if response.status_code != 200:
                _logger.error(
                    "Request to openstreetmap failed.\nCode: %s\nContent: %s",
                    response.status_code,
                    response.content,
                )
            return response.json()
        except Exception as e:
            self._raise_query_error(e)
