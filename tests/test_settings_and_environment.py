from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.engines.metadata_engine import MetadataEngine
from app.services.text_extraction_service import TextExtractionService
from app.settings import (
    AppSettings,
    ApplicationPaths,
    InvalidConfigurationError,
    SettingsService,
    ToolDetector,
    ToolState,
    ToolStatus,
)


def _paths(root: Path) -> ApplicationPaths:
    return ApplicationPaths(
        application_dir=root,
        resource_dir=root,
        config_dir=root / "config",
        temp_dir=root / "temp",
    )


def test_configuration_without_key_keeps_ip_lookup_disabled(tmp_path: Path) -> None:
    settings = SettingsService(
        tmp_path / "missing.json",
        environ={},
    ).load()

    assert settings.ip_api_key == ""
    assert settings.ip_lookup_enabled is False


def test_environment_key_overrides_local_configuration(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"ip_lookup_enabled": False, "request_timeout": 20}),
        encoding="utf-8",
    )

    settings = SettingsService(
        path,
        environ={
            "IP2LOCATION_API_KEY": "local-secret",
            "IP2LOCATION_ENABLED": "true",
        },
    ).load()

    assert settings.ip_api_key == "local-secret"
    assert settings.ip_lookup_enabled is True
    assert settings.request_timeout == 20


def test_legacy_json_secret_is_ignored_and_text_booleans_are_parsed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "ip_api_key": "legacy-placeholder",
                "ip_lookup_enabled": "false",
                "ocr_enabled": "false",
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsService(path, environ={}).load()

    assert settings.ip_api_key == ""
    assert settings.ip_lookup_enabled is False
    assert settings.ocr_enabled is False


def test_processing_limits_are_configurable(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "limits": {
                    "max_file_size_bytes": 1234,
                    "max_pdf_pages": 7,
                    "ocr_timeout_seconds": 9,
                }
            }
        ),
        encoding="utf-8",
    )

    settings = SettingsService(path, environ={}).load()

    assert settings.limits.max_file_size_bytes == 1234
    assert settings.limits.max_pdf_pages == 7
    assert settings.limits.ocr_timeout_seconds == 9


def test_secret_is_excluded_from_repr_serialization_and_logs(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = AppSettings(
        ip_api_key="do-not-persist",
        ip_lookup_enabled=True,
    )
    service = SettingsService(tmp_path / "settings.json", environ={})

    service.save(settings)
    serialized = (tmp_path / "settings.json").read_text(encoding="utf-8")

    assert "do-not-persist" not in repr(settings)
    assert "do-not-persist" not in serialized
    assert "do-not-persist" not in caplog.text
    assert "ip_api_key" not in settings.safe_dict()


@pytest.mark.parametrize(
    ("payload", "environment", "message"),
    [
        ({"request_timeout": "invalid"}, {}, "request_timeout deve ser inteiro"),
        ({"request_timeout": 0}, {}, "entre 1 e 120"),
        (
            {"ip_lookup_enabled": True},
            {},
            "IP2LOCATION_API_KEY não foi definida",
        ),
    ],
)
def test_invalid_configuration_has_clear_message(
    tmp_path: Path,
    payload: dict[str, object],
    environment: dict[str, str],
    message: str,
) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(InvalidConfigurationError, match=message):
        SettingsService(path, environ=environment).load()


def test_paths_do_not_depend_on_current_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    module = project / "app" / "settings" / "paths.py"
    elsewhere = tmp_path / "elsewhere"
    module.parent.mkdir(parents=True)
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    paths = ApplicationPaths.discover(module_file=module, environ={})

    assert paths.application_dir == project.resolve()
    assert paths.resource("app/ui/style.qss") == (
        project / "app/ui/style.qss"
    ).resolve()
    assert paths.settings_file == (project / "config/settings.json").resolve()


def test_bundled_paths_use_bundle_resources_and_user_configuration(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    executable = tmp_path / "installed" / "ForensiHash.exe"
    local_data = tmp_path / "local-data"

    paths = ApplicationPaths.discover(
        bundle_dir=bundle,
        executable=executable,
        environ={"LOCALAPPDATA": str(local_data)},
    )

    assert paths.bundled is True
    assert paths.resource_dir == bundle.resolve()
    assert paths.application_dir == executable.resolve().parent
    assert paths.config_dir == (local_data / "ForensiHashPro").resolve()


def test_resource_path_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="relativo e seguro"):
        _paths(tmp_path).resource("../secret.txt")


def test_tool_detector_distinguishes_available_invalid_missing_and_disabled(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "tesseract.exe"
    executable.write_bytes(b"test executable placeholder")

    available = ToolDetector(
        _paths(tmp_path),
        environ={"FORENSIHASH_TESSERACT_PATH": str(executable)},
        which=lambda _command: None,
    ).tesseract()
    invalid = ToolDetector(
        _paths(tmp_path),
        environ={"FORENSIHASH_TESSERACT_PATH": str(tmp_path / "absent.exe")},
        which=lambda _command: None,
    ).tesseract()
    missing = ToolDetector(
        _paths(tmp_path), environ={}, which=lambda _command: None
    ).tesseract()
    disabled = ToolDetector(_paths(tmp_path), environ={}).tesseract(enabled=False)

    assert available.state is ToolState.AVAILABLE
    assert invalid.state is ToolState.INVALID_PATH
    assert missing.state is ToolState.NOT_INSTALLED
    assert disabled.state is ToolState.DISABLED


@pytest.mark.skipif(os.name != "posix", reason="comportamento específico do Linux")
def test_poppler_configured_directory_uses_posix_executable_on_linux(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "poppler" / "pdftoppm"
    executable.parent.mkdir()
    executable.write_bytes(b"placeholder")
    status = ToolDetector(
        _paths(tmp_path),
        environ={"FORENSIHASH_POPPLER_PATH": str(executable.parent)},
        which=lambda _command: None,
    ).poppler()

    assert status.state is ToolState.AVAILABLE
    assert status.path == executable.parent.resolve()


@pytest.mark.skipif(os.name != "nt", reason="binário empacotado específico do Windows")
def test_metadata_engine_uses_resolved_exiftool_outside_project_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "project" / "tools" / "exiftool" / "exiftool.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"placeholder")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    status = ToolDetector(
        _paths(tmp_path / "project"), environ={}, which=lambda _command: None
    ).exiftool()

    engine = MetadataEngine(tool_status=status)

    assert engine.exiftool_path == executable.resolve()
    assert engine.exiftool_status.available


def test_missing_optional_python_ocr_dependency_has_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    available = ToolStatus(
        "Tesseract OCR", ToolState.AVAILABLE, Path("tesseract"), "available"
    )
    service = TextExtractionService(
        tesseract_status=available,
        poppler_status=available,
    )

    def missing_import(name: str):
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(
        "app.services.text_extraction_service.importlib.import_module",
        missing_import,
    )

    with pytest.raises(RuntimeError, match="pytesseract não está instalado"):
        service._image_to_string("image.png")
