# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from lxml import etree


def sat_str(value):
    """Normalize SAT/cfdiclient values to str.

    XML attributes are usually text; tests may pass int. This ensures a
    consistent str regardless of source.
    """
    if value is None:
        return ""
    return str(value).strip()


def sat_int(value, default=0):
    """Safely cast a SAT numeric status to int.

    cfdiclient returns raw SOAP attributes as-is (str or None).
    """
    if value is None or value == "":
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


# Secure XML parser for any module that processes CFDI/SAT payloads.
# Prevents XXE attacks by disabling entity resolution and network access.
SAFE_XML_PARSER = etree.XMLParser(resolve_entities=False, no_network=True)
