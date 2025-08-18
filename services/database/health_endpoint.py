"""Health endpoint for database validation (Task 2)."""

import logging
from typing import Dict, Any
from datetime import datetime

from .simple_health import check_database_health, check_pgvector_extension, check_tables_exist
from .pool import db_health_ok

logger = logging.getLogger(__name__)


def get_database_health_status() -> Dict[str, Any]:
    """
    Comprehensive database health check for GET /health/db endpoint.
    
    Returns:
        Dict containing health status, timing, and component checks
    """
    start_time = datetime.utcnow()
    
    try:
        # Quick connectivity check
        connectivity_ok = db_health_ok()
        
        # Detailed health checks
        db_health = check_database_health()
        pgvector_status = check_pgvector_extension()
        tables_status = check_tables_exist()
        
        # Calculate response time
        response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Determine overall status
        overall_status = "healthy"
        if not connectivity_ok:
            overall_status = "unhealthy"
        elif db_health.get("database", {}).get("status") != "healthy":
            overall_status = "degraded"
        elif tables_status.get("tables", {}).get("status") != "complete":
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "response_time_ms": round(response_time_ms, 2),
            "checks": {
                "connectivity": {
                    "status": "healthy" if connectivity_ok else "unhealthy",
                    "description": "Basic database connectivity test"
                },
                "database": db_health.get("database", {}),
                "pgvector": pgvector_status.get("pgvector", {}),
                "tables": tables_status.get("tables", {})
            },
            "version": "1.0.0",
            "component": "database-foundation"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "response_time_ms": round(response_time_ms, 2),
            "error": str(e),
            "checks": {},
            "version": "1.0.0",
            "component": "database-foundation"
        }


def validate_database_setup() -> bool:
    """
    Validate that database setup is complete and ready for use.
    
    Returns:
        True if database is fully configured and operational
    """
    try:
        health_status = get_database_health_status()
        
        # Check overall status
        if health_status["status"] not in ["healthy", "degraded"]:
            logger.error(f"Database health check failed: {health_status.get('error', 'Unknown error')}")
            return False
        
        # Check specific components
        checks = health_status.get("checks", {})
        
        # Connectivity is required
        if checks.get("connectivity", {}).get("status") != "healthy":
            logger.error("Database connectivity check failed")
            return False
        
        # Tables must exist
        tables_status = checks.get("tables", {}).get("status")
        if tables_status != "complete":
            missing_tables = checks.get("tables", {}).get("missing", [])
            logger.error(f"Required tables missing: {missing_tables}")
            return False
        
        # pgvector should be available (warning if not)
        pgvector_status = checks.get("pgvector", {}).get("status")
        if pgvector_status != "available":
            logger.warning("pgvector extension not available - vector operations will fail")
        
        logger.info("Database setup validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Database validation failed: {e}")
        return False


if __name__ == "__main__":
    # Quick validation script
    import json
    
    print("=== Database Health Check ===")
    health = get_database_health_status()
    print(json.dumps(health, indent=2))
    
    print("\n=== Database Setup Validation ===")
    is_valid = validate_database_setup()
    print(f"Database setup valid: {is_valid}")