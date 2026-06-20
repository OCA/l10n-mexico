# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from pytz import timezone

# Timezone used for SAT date logic across all SAT-consuming modules.
MX_TZ = timezone("America/Mexico_City")

# SAT web service response codes (shared across Solicitud, Verificacion, Descarga).
SAT_CODE_SUCCESS = "5000"
SAT_CODE_NO_INFO = "5004"
SAT_CODE_MAX_ELEMENTS = "5003"
SAT_CODE_DUPLICATE_LIFETIME = "5002"
SAT_CODE_DAILY_LIMIT = "5011"
SAT_REJECT_CODES = frozenset({"5001", "5002", "5005", "404"})

# SAT DescargaMasiva - package-level error codes (V1.5)
SAT_DOWNLOAD_EXPIRED = "5007"
SAT_DOWNLOAD_MAX_REACHED = "5008"

# SAT EstadoSolicitud values (VerificaSolicitudDescarga)
SAT_REQUEST_STATUS_ACCEPTED = 1
SAT_REQUEST_STATUS_PROCESSING = 2
SAT_REQUEST_STATUS_READY = 3
SAT_REQUEST_STATUS_ERROR = 4
SAT_REQUEST_STATUS_REJECTED = 5
SAT_REQUEST_STATUS_EXPIRED = 6
SAT_REQUEST_STATUS_LABELS = {
    SAT_REQUEST_STATUS_ACCEPTED: "Accepted",
    SAT_REQUEST_STATUS_PROCESSING: "In progress",
    SAT_REQUEST_STATUS_READY: "Completed",
    SAT_REQUEST_STATUS_ERROR: "Error",
    SAT_REQUEST_STATUS_REJECTED: "Rejected",
    SAT_REQUEST_STATUS_EXPIRED: "Expired",
}

# SAT CodEstatus / CodigoEstadoSolicitud labels for user-facing messages.
SAT_STATUS_CODE_LABELS = {
    SAT_CODE_SUCCESS: "Successful",
    SAT_CODE_NO_INFO: "No information",
    SAT_CODE_MAX_ELEMENTS: "Maximum number of elements exceeded",
    SAT_CODE_DUPLICATE_LIFETIME: "Duplicate request",
    SAT_CODE_DAILY_LIMIT: "Daily limit reached",
}

# Default sync window when no company configuration exists.
SAT_DEFAULT_SYNC_DAYS = 30

# Metadata sync uses smaller windows to avoid SAT 5003 (1M records).
SAT_METADATA_DEFAULT_WINDOW_DAYS = 7
SAT_METADATA_MIN_WINDOW_HOURS = 1
