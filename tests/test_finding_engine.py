from app.engines.finding_engine import FindingsEngine
from app.models import MetadataResult


def test_detect_itext_finding() -> None:
    metadata = MetadataResult(
        raw={
            "PDF:Producer": "iText 7.1.15",
        }
    )

    engine = FindingsEngine()
    findings = engine.analyze(metadata)

    assert len(findings) == 1
    assert findings[0].title == "Vestígio de processamento por iText"


def test_detect_gps_finding() -> None:
    metadata = MetadataResult(
        raw={
            "EXIF:GPSLatitude": "22 deg 54' 12.00\" S",
            "EXIF:GPSLongitude": "43 deg 10' 10.00\" W",
        }
    )

    engine = FindingsEngine()
    findings = engine.analyze(metadata)

    assert len(findings) == 1
    assert findings[0].title == "Metadados GPS encontrados"