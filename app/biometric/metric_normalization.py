from typing import Final


AWARE_METRIC_ALIASES: Final[dict[str, tuple[str, str | None]]] = {
    "IMAGE_WIDTH": ("image.width_pixels", "pixels"),
    "IMAGE_HEIGHT": ("image.height_pixels", "pixels"),
    "FILE_SIZE": ("file.size_bytes", "bytes"),
    "EYE_SEPARATION": ("face.eye_separation_pixels", "pixels"),
    "POSE_ANGLE_YAW": ("face.pose.yaw_degrees", "degrees"),
    "POSE_ANGLE_PITCH": ("face.pose.pitch_degrees", "degrees"),
    "EYE_AXIS_ANGLE": ("face.pose.roll_degrees", "degrees"),
    "BRIGHTNESS_SCORE": ("image.brightness_score", None),
    "SHARPNESS_LIKELIHOOD": ("image.sharpness_likelihood", None),
    "FOCUS_LIKELIHOOD": ("image.focus_likelihood", None),
    "MASK_LIKELIHOOD": ("face.mask_likelihood", None),
    "DARK_GLASSES_LIKELIHOOD": ("face.dark_glasses_likelihood", None),
}

XML_METRIC_NAMES: Final[dict[str, str]] = {
    "pose_angle_yaw": "POSE_ANGLE_YAW",
    "pose_angle_pitch": "POSE_ANGLE_PITCH",
    "facial_dynamic_range": "FACIAL_DYNAMIC_RANGE",
    "left_eye_closed_likelihood": "LEFT_EYE_CLOSED_LIKELIHOOD",
    "right_eye_closed_likelihood": "RIGHT_EYE_CLOSED_LIKELIHOOD",
    "dark_glasses_likelihood": "DARK_GLASSES_LIKELIHOOD",
    "image_width": "IMAGE_WIDTH",
    "image_height": "IMAGE_HEIGHT",
    "eye_separation": "EYE_SEPARATION",
    "eye_axis_angle": "EYE_AXIS_ANGLE",
    "eye_axis_location_ratio": "EYE_AXIS_LOCATION_RATIO",
    "centerline_location_ratio": "CENTERLINE_LOCATION_RATIO",
    "image_width_to_head_width_ratio": "IMAGE_WIDTH_TO_HEAD_WIDTH_RATIO",
    "head_height_to_image_height_ratio": "HEAD_HEIGHT_TO_IMAGE_HEIGHT_RATIO",
    "image_format": "IMAGE_FORMAT",
    "jpeg_quality_level": "JPEG_QUALITY_LEVEL",
}


def normalize_aware_metric(name: str) -> tuple[str | None, str | None]:
    return AWARE_METRIC_ALIASES.get(name, (None, None))


def normalize_aware_profile_metric(
    name: str,
) -> tuple[str | None, str | None]:
    metric_name = XML_METRIC_NAMES.get(name)
    if metric_name is None:
        return None, None
    canonical_name, unit = normalize_aware_metric(metric_name)
    return canonical_name or metric_name, unit
