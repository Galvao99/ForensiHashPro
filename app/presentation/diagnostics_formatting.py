from __future__ import annotations


def format_bytes(value: int | None) -> str:
    if value is None:
        return "—"
    units = ("B", "KB", "MB", "GB", "TB")
    amount = float(max(0, value))
    unit = units[0]
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            break
        amount /= 1024
    if unit == "B":
        return f"{int(amount)} B"
    return f"{amount:.1f} {unit}".replace(".", ",")


def format_duration(value_ms: float | None) -> str:
    if value_ms is None:
        return "—"
    value = max(0.0, value_ms)
    if value < 1000:
        return f"{value:.0f} ms"
    if value < 60_000:
        return f"{value / 1000:.2f} s".replace(".", ",")
    return f"{value / 60_000:.2f} min".replace(".", ",")


def format_count(value: int, singular: str, plural: str | None = None) -> str:
    return f"{value} {singular if value == 1 else (plural or singular + 's')}"
