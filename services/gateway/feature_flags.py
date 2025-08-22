import os

def is_feature_enabled(feature_name: str) -> bool:
    """
    Check if a feature is enabled based on an environment variable.
    Feature flags are expected to be in the format `FEATURE_{feature_name}`.
    For example, to enable the `NEW_QUERY_ENDPOINT` feature, set the
    `FEATURE_NEW_QUERY_ENDPOINT` environment variable to `true`.
    """
    flag_name = f"FEATURE_{feature_name.upper()}"
    return os.getenv(flag_name, "false").lower() == "true"