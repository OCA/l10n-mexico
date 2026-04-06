# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from pytz import timezone

# Timezone used for SAT date logic across all SAT-consuming modules.
MX_TZ = timezone("America/Mexico_City")

# SAT web service response codes (shared across Solicitud, Verificacion, Descarga).
SAT_CODE_SUCCESS = "5000"
SAT_CODE_NO_INFO = "5004"
SAT_REJECT_CODES = frozenset({"5001", "5002", "5005", "404"})
