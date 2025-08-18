import os
from psycopg_pool import ConnectionPool

_POOL = None

def _dsn():
    return os.getenv("DATABASE_URL") or os.getenv("ALLOYDB_CONNECTION_STRING")

def get_pool():
    """Create pool only if QUERY_MODE != web_only."""
    if os.getenv("QUERY_MODE", "hybrid").lower() == "web_only":
        raise RuntimeError("DB disabled in web_only mode")
    global _POOL
    if _POOL is None:
        dsn = _dsn()
        if not dsn:
            raise RuntimeError("DATABASE_URL/ALLOYDB_CONNECTION_STRING not set")
        _POOL = ConnectionPool(dsn, min_size=1, max_size=10, timeout=10, kwargs={"prepare_threshold":0})
    return _POOL

def get_connection():
    """Convenience for callers that need an actual connection."""
    return get_pool().connection()
