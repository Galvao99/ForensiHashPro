import pytest

from app.models.detected_ip import (
    IpClassification,
)
from app.services.ip_extraction_service import (
    IpExtractionService,
)


@pytest.fixture
def service() -> IpExtractionService:
    return IpExtractionService()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Endereço utilizado: 179.107.132.93",
            "179.107.132.93",
        ),
        (
            "IP interno: 10.200.53.160",
            "10.200.53.160",
        ),
        (
            "Gateway: 192.168.0.1",
            "192.168.0.1",
        ),
        (
            "Loopback: 127.0.0.1",
            "127.0.0.1",
        ),
    ],
)
def test_extract_valid_ipv4(
    service: IpExtractionService,
    text: str,
    expected: str,
) -> None:
    results = service.extract(text)

    assert len(results) == 1
    assert results[0].address == expected
    assert results[0].version == 4


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "IPv6: 2804:388:a013:ecc:0:6e:f695:ed01",
            "2804:388:a013:ecc:0:6e:f695:ed01",
        ),
        (
            "Servidor: 2001:db8::1",
            "2001:db8::1",
        ),
        (
            "Loopback IPv6: ::1",
            "::1",
        ),
        (
            "Não especificado: ::",
            "::",
        ),
        (
            "IPv4 mapeado: ::ffff:192.0.2.128",
            "::ffff:c000:280",
        ),
    ],
)
def test_extract_valid_ipv6(
    service: IpExtractionService,
    text: str,
    expected: str,
) -> None:
    results = service.extract(text)

    assert len(results) == 1
    assert results[0].address == expected
    assert results[0].version == 6


@pytest.mark.parametrize(
    "text",
    [
        "IP inválido: 999.999.999.999",
        "IP incompleto: 192.168.1",
        "Versão do aplicativo: 1.2.3",
        "Sequência: 1.2.3.4.5",
        "Data: 15/07/2026",
        "Hash: a42c67dd220cc55791f7e391c4470ab6",
        "Número: 12345678901234567890",
    ],
)
def test_reject_invalid_candidates(
    service: IpExtractionService,
    text: str,
) -> None:
    assert service.extract(text) == []


def test_preserve_raw_ipv6_text(
    service: IpExtractionService,
) -> None:
    text = (
        "IPv6 informado: "
        "2001:0DB8:0000:0000:0000:0000:0000:0001"
    )

    result = service.extract(text)[0]

    assert result.raw_text == (
        "2001:0DB8:0000:0000:0000:0000:0000:0001"
    )
    assert result.address == "2001:db8::1"


def test_extract_multiple_ips(
    service: IpExtractionService,
) -> None:
    text = (
        "IPv4: 179.107.132.93. "
        "IPv6: 2804:388:a013:ecc:0:6e:f695:ed01."
    )

    results = service.extract(text)

    assert [
        result.address
        for result in results
    ] == [
        "179.107.132.93",
        "2804:388:a013:ecc:0:6e:f695:ed01",
    ]


def test_preserve_repeated_occurrences(
    service: IpExtractionService,
) -> None:
    text = (
        "Primeiro acesso: 179.107.132.93. "
        "Segundo acesso: 179.107.132.93."
    )

    results = service.extract(text)

    assert len(results) == 2
    assert results[0].address == results[1].address
    assert results[0].start != results[1].start


def test_extract_unique_addresses(
    service: IpExtractionService,
) -> None:
    text = (
        "IP inicial: 179.107.132.93. "
        "IP final: 179.107.132.93."
    )

    results = service.extract_unique(text)

    assert len(results) == 1
    assert results[0].address == "179.107.132.93"


def test_preserve_context(
    service: IpExtractionService,
) -> None:
    text = (
        "Durante a contratação eletrônica, "
        "foi registrado o endereço IP 179.107.132.93 "
        "na trilha de auditoria apresentada."
    )

    result = service.extract(text)[0]

    assert "contratação eletrônica" in result.context
    assert "trilha de auditoria" in result.context


def test_preserve_positions(
    service: IpExtractionService,
) -> None:
    text = "Endereço IP: 179.107.132.93."

    result = service.extract(text)[0]

    assert text[result.start:result.end] == (
        "179.107.132.93"
    )


@pytest.mark.parametrize(
    ("address", "classification"),
    [
        (
            "179.107.132.93",
            IpClassification.PUBLIC,
        ),
        (
            "10.200.53.160",
            IpClassification.PRIVATE,
        ),
        (
            "192.168.0.1",
            IpClassification.PRIVATE,
        ),
        (
            "127.0.0.1",
            IpClassification.LOOPBACK,
        ),
        (
            "169.254.10.20",
            IpClassification.LINK_LOCAL,
        ),
        (
            "224.0.0.1",
            IpClassification.MULTICAST,
        ),
        (
            "0.0.0.0",
            IpClassification.UNSPECIFIED,
        ),
        (
            "100.64.0.1",
            IpClassification.CGNAT,
        ),
        (
            "::1",
            IpClassification.LOOPBACK,
        ),
        (
            "fe80::1",
            IpClassification.LINK_LOCAL,
        ),
        (
            "ff02::1",
            IpClassification.MULTICAST,
        ),
        (
            "::",
            IpClassification.UNSPECIFIED,
        ),
    ],
)
def test_classify_ips(
    service: IpExtractionService,
    address: str,
    classification: IpClassification,
) -> None:
    result = service.extract(
        f"Endereço: {address}"
    )[0]

    assert result.classification == classification


def test_group_occurrences(
    service: IpExtractionService,
) -> None:
    text = (
        "IP A: 179.107.132.93. "
        "IP B: 10.200.53.160. "
        "IP A novamente: 179.107.132.93."
    )

    grouped = service.group_occurrences(
        service.extract(text)
    )

    assert len(grouped["179.107.132.93"]) == 2
    assert len(grouped["10.200.53.160"]) == 1


def test_empty_text(
    service: IpExtractionService,
) -> None:
    assert service.extract("") == []
    assert service.extract("   ") == []
    assert service.extract(None) == []


def test_invalid_context_radius() -> None:
    with pytest.raises(
        ValueError,
        match="context_radius",
    ):
        IpExtractionService(
            context_radius=-1
        )

@pytest.mark.parametrize(
    "suffix",
    [
        ".",
        ",",
        ";",
        ":",
        ")",
        "]",
        "\n",
    ],
)
def test_extract_ipv4_followed_by_punctuation(
    service: IpExtractionService,
    suffix: str,
) -> None:
    text = f"IP registrado: 179.107.132.93{suffix}"

    results = service.extract(text)

    assert len(results) == 1
    assert results[0].address == "179.107.132.93"
    assert results[0].raw_text == "179.107.132.93"


def test_do_not_extract_ipv4_from_five_part_sequence(
    service: IpExtractionService,
) -> None:
    results = service.extract(
        "Versão técnica: 1.2.3.4.5"
    )

    assert results == []


def test_extract_complete_ipv4_mapped_ipv6(
    service: IpExtractionService,
) -> None:
    text = "IPv4 mapeado: ::ffff:192.0.2.128"

    results = service.extract(text)

    assert len(results) == 1
    assert results[0].raw_text == "::ffff:192.0.2.128"
    assert results[0].address == "::ffff:c000:280"
    assert results[0].version == 6