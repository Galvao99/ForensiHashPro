from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Badge:
    """
    Representa um badge visual utilizado na interface.

    Os badges servem para destacar informações curtas,
    como algoritmos, datas, tipos de arquivo, status,
    producers, IPs e demais evidências técnicas.
    """

    text: str
    color: str = "gray"
    icon: str = ""
    tooltip: str = ""

def success_badge(
    text: str,
    tooltip: str = "",
) -> Badge:
    return Badge(
        text=text,
        color="green",
        icon="check",
        tooltip=tooltip,
    )


def warning_badge(
    text: str,
    tooltip: str = "",
) -> Badge:
    return Badge(
        text=text,
        color="orange",
        icon="warning",
        tooltip=tooltip,
    )


def danger_badge(
    text: str,
    tooltip: str = "",
) -> Badge:
    return Badge(
        text=text,
        color="red",
        icon="error",
        tooltip=tooltip,
    )


def info_badge(
    text: str,
    tooltip: str = "",
) -> Badge:
    return Badge(
        text=text,
        color="blue",
        icon="info",
        tooltip=tooltip,
    )


def neutral_badge(
    text: str,
    tooltip: str = "",
) -> Badge:
    return Badge(
        text=text,
        color="gray",
        icon="",
        tooltip=tooltip,
    )