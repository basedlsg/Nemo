"""Database connection manager with fallback strategies."""
import logging
import os
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ConnectionStrategy(Enum):
    """Database connection strategies."""
    DIRECT_POSTGRESQL = "direct_postgresql"
    SQLITE_FALLBACK = "sqlite_fallback"


@dataclass
class ConnectionResult:
    """Result of connection attempt."""
    strategy: ConnectionStrategy
    success: bool
    error_message: Optional[str]
    health_info: Dict[str, Any]


class DatabaseConnectionManager:
    """Manages database connections with fallback strategies."""
    
    def __init__(self):
        self.current_strategy = None
        self.current_connection = None
        self._cached_health = None
    
    async def get_connection_info(self) -> ConnectionResult:
        """Get current database connection information."""
        database_url = os.getenv("DATABASE_URL")
        
        if not database_url:
            # No PostgreSQL URL, use SQLite fallback
            return await self._try_sqlite_fallback()
        
        # Try PostgreSQL first
        postgresql_result = await self._try_postgresql(database_url)
        if postgresql_result.success:
            return postgresql_result
        
        # PostgreSQL failed, try SQLite fallback
        logger.warning(f"PostgreSQL connection failed: {postgresql_result.error_message}")
        return await self._try_sqlite_fallback()
    
    async def _try_postgresql(self, database_url: str) -> ConnectionResult:
        """Try PostgreSQL connection."""
        try:
            from services.database.network_diagnostics import test_database_connectivity
            from services.database.init import check_database_health
            
            # Test network connectivity first
            network_report = await test_database_connectivity(database_url)
            
            if network_report.overall_status.value == "success":
                # Network is good, test database health
                health_result = await check_database_health(database_url)
                
                if health_result["status"] == "healthy":
                    self.current_strategy = ConnectionStrategy.DIRECT_POSTGRESQL
                    return ConnectionResult(
                        strategy=ConnectionStrategy.DIRECT_POSTGRESQL,
                        success=True,
                        error_message=None,
                        health_info={
                            "connection_type": "postgresql",
                            "network_status": network_report.overall_status.value,
                            **health_result
                        }
                    )
                else:
                    return ConnectionResult(
                        strategy=ConnectionStrategy.DIRECT_POSTGRESQL,
                        success=False,
                        error_message=f"Database health check failed: {health_result.get('error', 'unknown')}",
                        health_info=health_result
                    )
            else:
                return ConnectionResult(
                    strategy=ConnectionStrategy.DIRECT_POSTGRESQL,
                    success=False,
                    error_message=f"Network connectivity failed: {network_report.overall_status.value}",
                    health_info={
                        "connection_type": "postgresql",
                        "network_status": network_report.overall_status.value,
                        "network_recommendations": network_report.recommendations
                    }
                )
                
        except Exception as e:
            return ConnectionResult(
                strategy=ConnectionStrategy.DIRECT_POSTGRESQL,
                success=False,
                error_message=f"PostgreSQL connection error: {str(e)}",
                health_info={"error": str(e)}
            )
    
    async def _try_sqlite_fallback(self) -> ConnectionResult:
        """Try SQLite fallback connection."""
        try:
            from services.database.sqlite_fallback import get_sqlite_fallback_db
            
            db = await get_sqlite_fallback_db()
            health_info = await db.get_health_info()
            
            if health_info["status"] == "healthy":
                self.current_strategy = ConnectionStrategy.SQLITE_FALLBACK
                return ConnectionResult(
                    strategy=ConnectionStrategy.SQLITE_FALLBACK,
                    success=True,
                    error_message=None,
                    health_info={
                        "connection_type": "sqlite_fallback",
                        **health_info
                    }
                )
            else:
                return ConnectionResult(
                    strategy=ConnectionStrategy.SQLITE_FALLBACK,
                    success=False,
                    error_message=f"SQLite fallback failed: {health_info.get('error', 'unknown')}",
                    health_info=health_info
                )
                
        except Exception as e:
            return ConnectionResult(
                strategy=ConnectionStrategy.SQLITE_FALLBACK,
                success=False,
                error_message=f"SQLite fallback error: {str(e)}",
                health_info={"error": str(e)}
            )
    
    async def search_regulatory_data(self, query: str, province: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Search regulatory data using current connection strategy."""
        connection_result = await self.get_connection_info()
        
        if not connection_result.success:
            return {
                "error": f"No database connection available: {connection_result.error_message}",
                "connection_strategy": connection_result.strategy.value
            }
        
        try:
            if connection_result.strategy == ConnectionStrategy.SQLITE_FALLBACK:
                from services.database.sqlite_fallback import get_sqlite_fallback_db
                db = await get_sqlite_fallback_db()
                results = await db.search_citations(query, province, limit)
                
                return {
                    "connection_strategy": "sqlite_fallback",
                    "results": results,
                    "total_results": len(results),
                    "query": query,
                    "province_filter": province
                }
            
            elif connection_result.strategy == ConnectionStrategy.DIRECT_POSTGRESQL:
                # TODO: Implement PostgreSQL search when connection is working
                return {
                    "connection_strategy": "postgresql",
                    "results": [],
                    "total_results": 0,
                    "query": query,
                    "province_filter": province,
                    "note": "PostgreSQL search not yet implemented"
                }
            
        except Exception as e:
            return {
                "error": f"Search failed: {str(e)}",
                "connection_strategy": connection_result.strategy.value
            }
    
    async def get_provinces(self) -> Dict[str, Any]:
        """Get list of provinces using current connection strategy."""
        connection_result = await self.get_connection_info()
        
        if not connection_result.success:
            return {
                "error": f"No database connection available: {connection_result.error_message}",
                "connection_strategy": connection_result.strategy.value
            }
        
        try:
            if connection_result.strategy == ConnectionStrategy.SQLITE_FALLBACK:
                from services.database.sqlite_fallback import get_sqlite_fallback_db
                db = await get_sqlite_fallback_db()
                provinces = await db.get_provinces()
                
                return {
                    "connection_strategy": "sqlite_fallback",
                    "provinces": provinces,
                    "total_provinces": len(provinces)
                }
            
            elif connection_result.strategy == ConnectionStrategy.DIRECT_POSTGRESQL:
                # TODO: Implement PostgreSQL provinces when connection is working
                return {
                    "connection_strategy": "postgresql",
                    "provinces": [],
                    "total_provinces": 0,
                    "note": "PostgreSQL provinces not yet implemented"
                }
                
        except Exception as e:
            return {
                "error": f"Failed to get provinces: {str(e)}",
                "connection_strategy": connection_result.strategy.value
            }
    
    async def get_asset_types(self) -> Dict[str, Any]:
        """Get list of asset types using current connection strategy."""
        connection_result = await self.get_connection_info()
        
        if not connection_result.success:
            return {
                "error": f"No database connection available: {connection_result.error_message}",
                "connection_strategy": connection_result.strategy.value
            }
        
        try:
            if connection_result.strategy == ConnectionStrategy.SQLITE_FALLBACK:
                from services.database.sqlite_fallback import get_sqlite_fallback_db
                db = await get_sqlite_fallback_db()
                asset_types = await db.get_asset_types()
                
                return {
                    "connection_strategy": "sqlite_fallback",
                    "asset_types": asset_types,
                    "total_asset_types": len(asset_types)
                }
            
            elif connection_result.strategy == ConnectionStrategy.DIRECT_POSTGRESQL:
                # TODO: Implement PostgreSQL asset types when connection is working
                return {
                    "connection_strategy": "postgresql",
                    "asset_types": [],
                    "total_asset_types": 0,
                    "note": "PostgreSQL asset types not yet implemented"
                }
                
        except Exception as e:
            return {
                "error": f"Failed to get asset types: {str(e)}",
                "connection_strategy": connection_result.strategy.value
            }


# Global instance
_connection_manager = None


def get_connection_manager() -> DatabaseConnectionManager:
    """Get or create database connection manager instance."""
    global _connection_manager
    
    if _connection_manager is None:
        _connection_manager = DatabaseConnectionManager()
    
    return _connection_manager
