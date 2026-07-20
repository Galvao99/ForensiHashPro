from typing import Final


AWARE_METRIC_ALIASES: Final[dict[str, tuple[str, str | None]]] = {
    "imageWidth": ("image.width_pixels", "pixels"),
    "imageHeight": ("image.height_pixels", "pixels"),
    "fileSize": ("file.size_bytes", "bytes"),
    "eyeSeparation": ("face.eye_separation_pixels", "pixels"),
    "yaw": ("face.pose.yaw_degrees", "degrees"),
    "pitch": ("face.pose.pitch_degrees", "degrees"),
    "roll": ("face.pose.roll_degrees", "degrees"),
    "brightness": ("image.brightness", None),
    "sharpness": ("image.sharpness", None),
}


def normalize_aware_metric(name: str) -> tuple[str | None, str | None]:
    return AWARE_METRIC_ALIASES.get(name, (None, None))

