from dataclasses import dataclass
from datetime import datetime


@dataclass
class TimelineEvent:
    title: str
    date: datetime
    description: str
    source: str
    color: str
    severity: str = "info"

    def formatted_date(self) -> str:
        return self.date.strftime("%d/%m/%Y %H:%M:%S")