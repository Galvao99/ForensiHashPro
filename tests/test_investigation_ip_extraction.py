from pathlib import Path
from types import SimpleNamespace

from app.investigation.investigation_context_builder import (
    InvestigationContextBuilder,
)


def _make_result(
    *,
    file_path: Path,
    extracted_text: str,
):
    """
    Cria um resultado mínimo compatível com o builder,
    sem precisar executar a análise real do arquivo.
    """

    return SimpleNamespace(
        file_info=SimpleNamespace(
            path=file_path,
            name=file_path.name,
        ),
        extracted_text=extracted_text,
        hashes=None,
        hash_result=None,
        metadata=None,
        digital_signature=None,
        timeline_events=None,
        json_analysis=None,
        detected_ips=None,
        ip_results=None,
    )


def test_builder_extracts_ipv4_from_text(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "contrato.pdf"
    file_path.touch()

    result = _make_result(
        file_path=file_path,
        extracted_text=(
            "Endereço IP utilizado durante a contratação: "
            "189.27.220.123"
        ),
    )

    context = InvestigationContextBuilder().build(
        [result]
    )

    evidence_key = str(file_path.resolve())

    assert context.detected_ips[evidence_key] == [
        "189.27.220.123"
    ]

    details = context.detected_ip_details[
        evidence_key
    ]

    assert len(details) == 1
    assert details[0].address == "189.27.220.123"
    assert details[0].version == 4
    assert "contratação" in details[0].context


def test_builder_extracts_ipv4_and_ipv6(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "protocolo.pdf"
    file_path.touch()

    result = _make_result(
        file_path=file_path,
        extracted_text=(
            "IPv4: 189.27.220.123. "
            "IPv6: 2804:388:a013:ecc:0:6e:f695:ed01."
        ),
    )

    context = InvestigationContextBuilder().build(
        [result]
    )

    evidence_key = str(file_path.resolve())

    assert context.detected_ips[evidence_key] == [
        "189.27.220.123",
        "2804:388:a013:ecc:0:6e:f695:ed01",
    ]

    assert len(
        context.detected_ip_details[evidence_key]
    ) == 2


def test_structured_ip_has_priority_without_duplication(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "contrato.pdf"
    file_path.touch()

    result = _make_result(
        file_path=file_path,
        extracted_text=(
            "IP registrado: 189.27.220.123"
        ),
    )

    result.detected_ips = [
        "189.27.220.123"
    ]

    context = InvestigationContextBuilder().build(
        [result]
    )

    evidence_key = str(file_path.resolve())

    assert context.detected_ips[evidence_key] == [
        "189.27.220.123"
    ]

    # A ocorrência estruturada não deve criar uma duplicata
    # artificial quando o mesmo IP já foi encontrado no texto.
    assert len(
        context.detected_ip_details[evidence_key]
    ) == 1


def test_repeated_ip_occurrences_are_preserved(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "logs.pdf"
    file_path.touch()

    result = _make_result(
        file_path=file_path,
        extracted_text=(
            "Primeiro acesso: 189.27.220.123. "
            "Segundo acesso: 189.27.220.123."
        ),
    )

    context = InvestigationContextBuilder().build(
        [result]
    )

    evidence_key = str(file_path.resolve())

    assert context.detected_ips[evidence_key] == [
        "189.27.220.123"
    ]

    assert len(
        context.detected_ip_details[evidence_key]
    ) == 2


def test_invalid_ip_does_not_enter_context(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "arquivo.pdf"
    file_path.touch()

    result = _make_result(
        file_path=file_path,
        extracted_text=(
            "Endereço informado: 999.999.999.999"
        ),
    )

    context = InvestigationContextBuilder().build(
        [result]
    )

    evidence_key = str(file_path.resolve())

    assert evidence_key not in context.detected_ips
    assert (
        evidence_key
        not in context.detected_ip_details
    )


def test_homonymous_files_keep_distinct_keys(
    tmp_path: Path,
) -> None:
    first_folder = tmp_path / "caso-a"
    second_folder = tmp_path / "caso-b"

    first_folder.mkdir()
    second_folder.mkdir()

    first_file = first_folder / "contrato.pdf"
    second_file = second_folder / "contrato.pdf"

    first_file.touch()
    second_file.touch()

    first_result = _make_result(
        file_path=first_file,
        extracted_text="IP: 189.27.220.123",
    )

    second_result = _make_result(
        file_path=second_file,
        extracted_text="IP: 10.200.53.160",
    )

    context = InvestigationContextBuilder().build(
        [
            first_result,
            second_result,
        ]
    )

    first_key = str(first_file.resolve())
    second_key = str(second_file.resolve())

    assert first_key != second_key

    assert context.detected_ips[first_key] == [
        "189.27.220.123"
    ]

    assert context.detected_ips[second_key] == [
        "10.200.53.160"
    ]