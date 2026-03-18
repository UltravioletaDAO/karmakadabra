"""
Platform Config Shim for KarmaKadabra (standalone mode)

When running outside the EM server context, all feature flags
default to True so that describe-net and other integrations
can be tested locally.
"""

import os


class PlatformConfig:
    """Lightweight feature flag stub."""

    # Feature flags can be overridden via env vars:
    # FEATURE_DESCRIBENET=false to disable
    _DEFAULTS = {
        "describenet": True,
    }

    @classmethod
    async def is_feature_enabled(cls, feature: str) -> bool:
        """Check if a feature is enabled (via env var or default)."""
        env_key = f"FEATURE_{feature.upper()}"
        env_val = os.environ.get(env_key)
        if env_val is not None:
            return env_val.lower() in ("true", "1", "yes")
        return cls._DEFAULTS.get(feature, False)
