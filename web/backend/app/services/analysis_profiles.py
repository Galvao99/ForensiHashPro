from __future__ import annotations

from app.analysis_profiles import (
    AnalysisProfile,
    FORENSIHASH_FREE,
    FORENSIHASH_PRO,
)
from web.backend.app.models import User, WebAnalysisProfile


class AnalysisEntitlementService:
    """Traduz entitlement persistido em capacidade técnica server-side."""

    @staticmethod
    def resolve(user: User) -> AnalysisProfile:
        return (
            FORENSIHASH_PRO
            if user.analysis_profile == WebAnalysisProfile.PRO.value
            else FORENSIHASH_FREE
        )
