"""Database health check utilities."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .connection import get_database, DatabaseManager
from .crud import QueryLogCRUD, EvaluationMetricCRUD, SourceCRUD

logger = logging.getLogger(__name__)


class DatabaseHealthChecker:
    """Comprehensive database health checking."""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager
    
    async def check_basic_connectivity(self) -> Dict[str, Any]:
        """Check basic database connectivity."""
        try:
            if not self.db_manager:
                self.db_manager = await get_database()
            
            start_time = datetime.utcnow()
            is_healthy = await self.db_manager.health_check()
            end_time = datetime.utcnow()
            
            latency_ms = int((end_time - start_time).total_seconds() * 1000)
            
            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "latency_ms": latency_ms,
                "timestamp": end_time.isoformat(),
                "details": "Basic connectivity check"
            }
        except Exception as e:
            logger.error(f"Database connectivity check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "details": "Basic connectivity check failed"
            }
    
    async def check_extensions(self) -> Dict[str, Any]:
        """Check required PostgreSQL extensions."""
        try:
            if not self.db_manager:
                self.db_manager = await get_database()
            
            async with self.db_manager.get_session() as session:
                # Check pgvector extension
                result = await session.execute(
                    text("SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'uuid-ossp')")
                )
                extensions = {row[0]: row[1] for row in result.fetchall()}
                
                required_extensions = ["vector", "uuid-ossp"]
                missing_extensions = [ext for ext in required_extensions if ext not in extensions]
                
                status = "healthy" if not missing_extensions else "degraded"
                
                return {
                    "status": status,
                    "extensions": extensions,
                    "missing_extensions": missing_extensions,
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": "Extension availability check"
                }
        except Exception as e:
            logger.error(f"Extension check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "details": "Extension check failed"
            }
    
    async def check_table_health(self) -> Dict[str, Any]:
        """Check table existence and basic statistics."""
        try:
            if not self.db_manager:
                self.db_manager = await get_database()
            
            async with self.db_manager.get_session() as session:
                # Check table existence and row counts
                tables_query = text("""
                    SELECT 
                        schemaname,
                        tablename,
                        n_tup_ins as inserts,
                        n_tup_upd as updates,
                        n_tup_del as deletes,
                        n_live_tup as live_rows,
                        n_dead_tup as dead_rows
                    FROM pg_stat_user_tables 
                    WHERE tablename IN ('citations', 'packs', 'sources', 'evaluation_metrics', 'query_logs', 'ingestion_jobs')
                    ORDER BY tablename
                """)
                
                result = await session.execute(tables_query)
                table_stats = []
                
                for row in result.fetchall():
                    table_stats.append({
                        "schema": row[0],
                        "table": row[1],
                        "inserts": row[2],
                        "updates": row[3],
                        "deletes": row[4],
                        "live_rows": row[5],
                        "dead_rows": row[6]
                    })
                
                return {
                    "status": "healthy",
                    "table_count": len(table_stats),
                    "tables": table_stats,
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": "Table health statistics"
                }
        except Exception as e:
            logger.error(f"Table health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "details": "Table health check failed"
            }
    
    async def check_data_freshness(self) -> Dict[str, Any]:
        """Check data freshness and ingestion pipeline health."""
        try:
            if not self.db_manager:
                self.db_manager = await get_database()
            
            async with self.db_manager.get_session() as session:
                # Check recent query activity
                recent_queries = await QueryLogCRUD.get_recent_stats(session, hours=24)
                
                # Check source crawl freshness
                stale_sources = await SourceCRUD.get_stale_sources(session, hours_threshold=48)
                
                # Check recent citations
                recent_citations_query = text("""
                    SELECT COUNT(*) as count, MAX(created_at) as latest
                    FROM citations 
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                """)
                result = await session.execute(recent_citations_query)
                row = result.fetchone()
                recent_citations_count = row[0] if row else 0
                latest_citation = row[1] if row else None
                
                freshness_score = "healthy"
                if len(stale_sources) > 5:  # More than 5 stale sources
                    freshness_score = "degraded"
                if recent_citations_count == 0:  # No recent citations
                    freshness_score = "stale"
                
                return {
                    "status": freshness_score,
                    "recent_queries": recent_queries,
                    "stale_sources_count": len(stale_sources),
                    "recent_citations_count": recent_citations_count,
                    "latest_citation": latest_citation.isoformat() if latest_citation else None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": "Data freshness and pipeline health"
                }
        except Exception as e:
            logger.error(f"Data freshness check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "details": "Data freshness check failed"
            }
    
    async def check_quality_metrics(self) -> Dict[str, Any]:
        """Check recent quality metrics and thresholds."""
        try:
            if not self.db_manager:
                self.db_manager = await get_database()
            
            async with self.db_manager.get_session() as session:
                provinces = ["shandong", "guangdong", "inner_mongolia"]
                province_readiness = {}
                
                for province in provinces:
                    # Check if province meets quality thresholds
                    is_ready = await EvaluationMetricCRUD.check_province_readiness(
                        session, province, "grid_connection"
                    )
                    
                    # Get latest metrics
                    latest_metrics = await EvaluationMetricCRUD.get_latest_by_province(
                        session, province
                    )
                    
                    province_readiness[province] = {
                        "ready": is_ready,
                        "latest_metrics_count": len(latest_metrics),
                        "latest_evaluation": latest_metrics[0].evaluation_date.isoformat() if latest_metrics else None
                    }
                
                overall_status = "healthy"
                ready_provinces = sum(1 for p in province_readiness.values() if p["ready"])
                if ready_provinces < len(provinces):
                    overall_status = "degraded"
                
                return {
                    "status": overall_status,
                    "ready_provinces": ready_provinces,
                    "total_provinces": len(provinces),
                    "province_readiness": province_readiness,
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": "Quality metrics and province readiness"
                }
        except Exception as e:
            logger.error(f"Quality metrics check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "details": "Quality metrics check failed"
            }
    
    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """Run all health checks and return comprehensive status."""
        checks = {
            "connectivity": await self.check_basic_connectivity(),
            "extensions": await self.check_extensions(),
            "tables": await self.check_table_health(),
            "data_freshness": await self.check_data_freshness(),
            "quality_metrics": await self.check_quality_metrics()
        }
        
        # Determine overall status
        statuses = [check["status"] for check in checks.values()]
        if "unhealthy" in statuses:
            overall_status = "unhealthy"
        elif "degraded" in statuses or "stale" in statuses:
            overall_status = "degraded"
        else:
            overall_status = "healthy"
        
        return {
            "overall_status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
            "summary": {
                "healthy_checks": sum(1 for s in statuses if s == "healthy"),
                "degraded_checks": sum(1 for s in statuses if s in ["degraded", "stale"]),
                "unhealthy_checks": sum(1 for s in statuses if s == "unhealthy"),
                "total_checks": len(checks)
            }
        }


async def get_database_health() -> Dict[str, Any]:
    """Get comprehensive database health status."""
    checker = DatabaseHealthChecker()
    return await checker.comprehensive_health_check()


async def get_basic_database_health() -> Dict[str, Any]:
    """Get basic database health status for quick checks."""
    checker = DatabaseHealthChecker()
    return await checker.check_basic_connectivity()


if __name__ == "__main__":
    # CLI tool for database health checking
    async def main():
        print("Running database health check...")
        health = await get_database_health()
        
        print(f"Overall Status: {health['overall_status']}")
        print(f"Timestamp: {health['timestamp']}")
        print(f"Summary: {health['summary']}")
        
        for check_name, check_result in health['checks'].items():
            print(f"\n{check_name.title()}: {check_result['status']}")
            if 'error' in check_result:
                print(f"  Error: {check_result['error']}")
    
    asyncio.run(main())