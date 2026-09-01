from __future__ import annotations

import os
from urllib.parse import urlsplit


ENVIRONMENTS = frozenset({"development", "test", "staging", "production"})
DEPLOYED_ENVIRONMENTS = frozenset({"staging", "production"})
DEFAULT_DEVELOPMENT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
DEFAULT_ANALYSIS_CONCURRENCY = 1
DEFAULT_ANALYSIS_QUEUE_CAPACITY = 20
DEFAULT_ANALYSIS_TIMEOUT_SECONDS = 300
DEFAULT_SESSION_LIFETIME_SECONDS = 8 * 60 * 60
DEFAULT_RESET_TOKEN_LIFETIME_SECONDS = 30 * 60


def environment() -> str:
    value = os.environ.get("FORENSIHASH_ENV", "development").strip().lower()
    if value not in ENVIRONMENTS:
        raise RuntimeError(
            "FORENSIHASH_ENV deve ser development, test, staging ou production."
        )
    return value


def deployed_environment() -> bool:
    return environment() in DEPLOYED_ENVIRONMENTS


def registration_enabled() -> bool:
    configured = os.environ.get("FORENSIHASH_REGISTRATION_ENABLED")
    if configured is None:
        return not deployed_environment()
    return _boolean("FORENSIHASH_REGISTRATION_ENABLED", configured)


def job_worker_enabled() -> bool:
    configured = os.environ.get("FORENSIHASH_JOB_WORKER_ENABLED")
    if configured is None:
        return deployed_environment()
    return _boolean("FORENSIHASH_JOB_WORKER_ENABLED", configured)


def analysis_concurrency() -> int:
    return _bounded_integer(
        "FORENSIHASH_ANALYSIS_CONCURRENCY",
        DEFAULT_ANALYSIS_CONCURRENCY,
        minimum=1,
        maximum=16,
    )


def analysis_queue_capacity() -> int:
    return _bounded_integer(
        "FORENSIHASH_ANALYSIS_QUEUE_CAPACITY",
        DEFAULT_ANALYSIS_QUEUE_CAPACITY,
        minimum=1,
        maximum=10_000,
    )


def analysis_timeout_seconds() -> int:
    return _bounded_integer(
        "FORENSIHASH_ANALYSIS_TIMEOUT_SECONDS",
        DEFAULT_ANALYSIS_TIMEOUT_SECONDS,
        minimum=1,
        maximum=86_400,
    )


def archive_limits():
    from app.parsers.archive import ArchiveLimits

    try:
        return ArchiveLimits.from_env()
    except ValueError as error:
        raise RuntimeError(str(error)) from error


def cookie_secure() -> bool:
    configured = os.environ.get("FORENSIHASH_COOKIE_SECURE")
    if configured is None:
        return deployed_environment()
    return _boolean("FORENSIHASH_COOKIE_SECURE", configured)


def cookie_samesite() -> str:
    value = os.environ.get("FORENSIHASH_COOKIE_SAMESITE", "lax").strip().lower()
    if value not in {"lax", "strict", "none"}:
        raise RuntimeError("FORENSIHASH_COOKIE_SAMESITE deve ser lax, strict ou none.")
    if value == "none" and not cookie_secure():
        raise RuntimeError("Cookies SameSite=none exigem FORENSIHASH_COOKIE_SECURE=true.")
    return value


def session_lifetime_seconds() -> int:
    return _bounded_integer("FORENSIHASH_SESSION_LIFETIME_SECONDS", DEFAULT_SESSION_LIFETIME_SECONDS, minimum=300, maximum=2_592_000)


def reset_token_lifetime_seconds() -> int:
    return _bounded_integer("FORENSIHASH_RESET_TOKEN_LIFETIME_SECONDS", DEFAULT_RESET_TOKEN_LIFETIME_SECONDS, minimum=300, maximum=86_400)


def application_base_url() -> str:
    value = os.environ.get("FORENSIHASH_APPLICATION_BASE_URL", "http://localhost:5173").strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise RuntimeError("FORENSIHASH_APPLICATION_BASE_URL deve ser uma URL HTTP(S) válida.")
    if deployed_environment() and parsed.scheme != "https":
        raise RuntimeError("FORENSIHASH_APPLICATION_BASE_URL deve usar HTTPS em staging/production.")
    return value


def allowed_origins() -> tuple[str, ...]:
    configured = os.environ.get("FORENSIHASH_ALLOWED_ORIGINS", "")
    if not configured.strip():
        if deployed_environment():
            raise RuntimeError("FORENSIHASH_ALLOWED_ORIGINS é obrigatório neste ambiente.")
        return DEFAULT_DEVELOPMENT_ORIGINS

    origins = tuple(dict.fromkeys(item.strip().rstrip("/") for item in configured.split(",") if item.strip()))
    if not origins:
        raise RuntimeError("FORENSIHASH_ALLOWED_ORIGINS não contém origins válidas.")
    for origin in origins:
        parsed = urlsplit(origin)
        if origin == "*" or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError(f"Origin CORS inválida: {origin!r}.")
        if parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise RuntimeError(f"Origin CORS deve conter somente scheme e host: {origin!r}.")
        if deployed_environment() and parsed.scheme != "https":
            raise RuntimeError("Origins de staging/production devem usar HTTPS.")
    return origins


def validate_runtime_configuration() -> None:
    current_environment = environment()
    allowed_origins()
    cookie_samesite()
    session_lifetime_seconds()
    reset_token_lifetime_seconds()
    application_base_url()
    archive_limits()
    if current_environment in DEPLOYED_ENVIRONMENTS:
        if not cookie_secure():
            raise RuntimeError(
                "FORENSIHASH_COOKIE_SECURE deve ser true em staging/production."
            )
        if not (os.environ.get("FORENSIHASH_DATABASE_URL") or os.environ.get("DATABASE_URL")):
            raise RuntimeError("A URL do PostgreSQL é obrigatória em staging/production.")


def _boolean(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} deve ser true ou false.")


def _bounded_integer(
    name: str, default: int, *, minimum: int, maximum: int
) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError(f"{name} deve ser um número inteiro.") from error
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} deve estar entre {minimum} e {maximum}.")
    return value
