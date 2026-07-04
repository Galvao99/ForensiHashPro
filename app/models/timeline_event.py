from dataclasses import dataclass
from datetime import datetime

from dataclasses import dataclass
from datetime import datetime

from app.enum.severity import Severity


@dataclass
class TimelineEvent:
    title: str
    date: datetime | None
    source: str
    description: str
    severity: Severity = Severity.INFO
    color: str = "#60A5FA"
    needs_confirmation: bool = False
    confirmed: bool = True

    def formatted_date(self) -> str:
        if not self.date:
            return "Data não identificada"

        return self.date.strftime("%d/%m/%Y %H:%M:%S")