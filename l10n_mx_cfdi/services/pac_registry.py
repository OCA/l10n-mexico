"""Registry of satcfdi PAC adapters and their capabilities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from satcfdi.pacs import Environment


@dataclass(frozen=True)
class PacProvider:
    code: str
    label: str
    module: str
    class_name: str
    supports_issue: bool
    supports_cancel: bool
    requires_signer_for_cancel: bool
    kwargs_builder: Callable[[Any, Environment], dict]


def _env(sandbox: bool) -> Environment:
    return Environment.TEST if sandbox else Environment.PRODUCTION


def _finkok_kwargs(service, environment: Environment) -> dict:
    return {
        "username": service.user,
        "password": service.password,
        "environment": environment,
    }


def _diverza_kwargs(service, environment: Environment) -> dict:
    return {
        "rfc": service.pac_rfc,
        "id": service.pac_client_id,
        "token": service.password or service.pac_token,
        "environment": environment,
    }


def _prodigia_kwargs(service, environment: Environment) -> dict:
    return {
        "user": service.user,
        "password": service.password,
        "contrato": service.pac_contrato,
        "environment": environment,
    }


def _comerciodigital_kwargs(service, environment: Environment) -> dict:
    return {
        "user": service.user,
        "password": service.password,
        "environment": environment,
    }


def _swsapien_kwargs(service, environment: Environment) -> dict:
    kwargs = {"environment": environment}
    if service.pac_token:
        kwargs["token"] = service.pac_token
    else:
        kwargs["user"] = service.user
        kwargs["password"] = service.password
    return kwargs


def _mysuite_kwargs(service, environment: Environment) -> dict:
    return {
        "requestor": service.pac_requestor,
        "country": service.pac_country or "MX",
        "user_name": service.user,
        "environment": environment,
    }


def _facturama_kwargs(service, environment: Environment) -> dict:
    return {
        "username": service.user,
        "password": service.password,
        "environment": environment,
    }


PAC_PROVIDERS: dict[str, PacProvider] = {
    "finkok": PacProvider(
        code="finkok",
        label="Finkok",
        module="satcfdi.pacs.finkok",
        class_name="Finkok",
        supports_issue=True,
        supports_cancel=True,
        requires_signer_for_cancel=True,
        kwargs_builder=_finkok_kwargs,
    ),
    "diverza": PacProvider(
        code="diverza",
        label="Diverza",
        module="satcfdi.pacs.diverza",
        class_name="Diverza",
        supports_issue=True,
        supports_cancel=True,
        requires_signer_for_cancel=False,
        kwargs_builder=_diverza_kwargs,
    ),
    "prodigia": PacProvider(
        code="prodigia",
        label="Prodigia",
        module="satcfdi.pacs.prodigia",
        class_name="Prodigia",
        supports_issue=False,
        supports_cancel=False,
        requires_signer_for_cancel=False,
        kwargs_builder=_prodigia_kwargs,
    ),
    "comerciodigital": PacProvider(
        code="comerciodigital",
        label="Comercio Digital",
        module="satcfdi.pacs.comerciodigital",
        class_name="ComercioDigital",
        supports_issue=False,
        supports_cancel=False,
        requires_signer_for_cancel=False,
        kwargs_builder=_comerciodigital_kwargs,
    ),
    "swsapien": PacProvider(
        code="swsapien",
        label="SW Sapien",
        module="satcfdi.pacs.swsapien",
        class_name="SWSapien",
        supports_issue=True,
        supports_cancel=True,
        requires_signer_for_cancel=False,
        kwargs_builder=_swsapien_kwargs,
    ),
    "mysuite": PacProvider(
        code="mysuite",
        label="MYSuite",
        module="satcfdi.pacs.mysuite",
        class_name="MYSuite",
        supports_issue=False,
        supports_cancel=False,
        requires_signer_for_cancel=False,
        kwargs_builder=_mysuite_kwargs,
    ),
    "facturama": PacProvider(
        code="facturama",
        label="Facturama",
        module="satcfdi.pacs.facturama",
        class_name="Facturama",
        supports_issue=True,
        supports_cancel=True,
        requires_signer_for_cancel=False,
        kwargs_builder=_facturama_kwargs,
    ),
}


def provider_selection():
    return [(code, provider.label) for code, provider in PAC_PROVIDERS.items()]


def get_provider(code: str) -> PacProvider:
    try:
        return PAC_PROVIDERS[code]
    except KeyError as exc:
        raise KeyError(f"Unknown PAC provider: {code}") from exc


def build_pac(service):
    """Instantiate the satcfdi PAC client for the given cfdi.service record."""
    import importlib

    provider = get_provider(service.provider)
    environment = _env(service.sandbox_mode)
    module = importlib.import_module(provider.module)
    cls = getattr(module, provider.class_name)
    pac = cls(**provider.kwargs_builder(service, environment))
    if provider.code == "facturama":
        from . import facturama_adapter

        pac = facturama_adapter.bind_enriched_issue(pac)
        pac = facturama_adapter.bind_enriched_cancel(pac)
    return pac
