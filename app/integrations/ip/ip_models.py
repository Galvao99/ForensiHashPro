from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IpLookupResult:
    ip: str
    provider: str = ""

    ip_version: str = ""
    network_type: str = ""
    is_public: bool = False

    country: str | None = None
    region: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    isp: str | None = None
    organization: str | None = None
    asn: str | None = None
    is_proxy: bool | None = None

    lookup_timestamp: datetime | None = None
    raw: dict | None = None

    lookup_performed: bool = True
    severity: str = "ok"
    message: str = ""

    @property
    def location_summary(self) -> str:
        if not self.lookup_performed:
            return "Não aplicável"

        parts = [self.city, self.region, self.country]
        return ", ".join(part for part in parts if part) or "Localização não identificada"

    @property
    def technical_summary(self) -> str:
        base = f"{self.ip} ({self.ip_version or 'versão não identificada'} / {self.network_type or 'tipo não identificado'})"

        if self.lookup_performed:
            return f"{base} — {self.location_summary}"

        return f"{base} — consulta externa não realizada"