from dataclasses import dataclass

@dataclass
class AppSettings:
    ip_provider: str = "ip2location"
    ip_api_key: str = ""
    request_timeout: int = 15