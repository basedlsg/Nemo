"""Simple database health check using connection pool."""

import logging
from typing import Dict, Any

from .pool import db_health_ok, get_health_info, get_connection

logger = logging.getLogger(__name__)


def check_database_health() -> Dict[str, Any]:
    """Check database connectivity and basic functionality."""
    return get_health_info()


def check_pgvector_extension() -> Dict[str, Any]:
    """Check if pgvector extension is available."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Check extension exists
                cur.execute(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
                )
                version_row = cur.fetchone()
                
                if not version_row:
                    return {
                        "status": "missing",
                        "error": "pgvector extension not installed"
                    }
                
                version = version_row[0]
                
                # Test vector operations
                cur.execute("SELECT '[1,2,3]'::vector")
                
                return {
                    "status": "healthy",
                    "version": version
                }
            
    except Exception as e:
        logger.error(f"pgvector health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


def check_required_tables() -> Dict[str, Any]:
    """Check if required tables exist."""
    try:
        required_tables = ["citations", "sources", "packs"]
        table_status = {}
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                for table in required_tables:
                    cur.execute(
                        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)",
                        (table,)
                    )
                    exists = cur.fetchone()[0]
                    table_status[table] = "exists" if exists else "missing"
        
        all_exist = all(status == "exists" for status in table_status.values())
        
        return {
            "status": "healthy" if all_exist else "degraded",
            "tables": table_status
        }
        
    except Exception as e:
        logger.error(f"Database tables check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


def get_comprehensive_health() -> Dict[str, Any]:
    """Get comprehensive database health status."""
    try:
        connectivity = check_database_health()
        extensions = check_pgvector_extension()
        tables = check_required_tables()
        
        # Determine overall status
        statuses = [connectivity["status"], extensions["status"], tables["status"]]
        
        if "unhealthy" in statuses:
            overall_status = "unhealthy"
        elif "degraded" in statuses or "missing" in statuses:
            overall_status = "degraded"
        else:
            overall_status = "healthy"
        
        return {
            "overall_status": overall_status,
            "connectivity": connectivity,
            "extensions": extensions,
            "tables": tables,
            "summary": {
                "healthy_checks": sum(1 for s in statuses if s == "healthy"),
                "degraded_checks": sum(1 for s in statuses if s in ["degraded", "missing"]),
                "unhealthy_checks": sum(1 for s in statuses if s == "unhealthy")
            }
        }
        
    except Exception as e:
        logger.error(f"Comprehensive health check failed: {e}")
        return {
            "overall_status": "unhealthy",
            "error": str(e)
        }