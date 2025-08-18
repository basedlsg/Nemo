"""Network diagnostics service for database connectivity troubleshooting."""
import asyncio
import logging
import socket
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectivityStatus(Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    CONNECTION_REFUSED = "connection_refused"
    DNS_FAILURE = "dns_failure"
    NETWORK_UNREACHABLE = "network_unreachable"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class NetworkTest:
    test_name: str
    status: ConnectivityStatus
    response_time_ms: Optional[int]
    error_message: Optional[str]
    details: Dict[str, Any]


@dataclass
class ConnectivityReport:
    target_host: str
    target_port: int
    overall_status: ConnectivityStatus
    tests: Dict[str, NetworkTest]
    recommendations: list[str]
    timestamp: str


class NetworkDiagnostics:
    """Network diagnostics service for database connectivity testing."""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
    
    async def test_tcp_connectivity(self, host: str, port: int) -> NetworkTest:
        """Test TCP connectivity to a host and port."""
        start_time = time.time()
        
        try:
            # Create socket connection with timeout
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            result = sock.connect_ex((host, port))
            response_time = int((time.time() - start_time) * 1000)
            
            sock.close()
            
            if result == 0:
                return NetworkTest(
                    test_name="tcp_connectivity",
                    status=ConnectivityStatus.SUCCESS,
                    response_time_ms=response_time,
                    error_message=None,
                    details={"connection_result": "success", "socket_error_code": 0}
                )
            else:
                status = ConnectivityStatus.CONNECTION_REFUSED
                if result == 10060:  # Windows timeout
                    status = ConnectivityStatus.TIMEOUT
                elif result == 10061:  # Windows connection refused
                    status = ConnectivityStatus.CONNECTION_REFUSED
                elif result == 10051:  # Network unreachable
                    status = ConnectivityStatus.NETWORK_UNREACHABLE
                
                return NetworkTest(
                    test_name="tcp_connectivity",
                    status=status,
                    response_time_ms=response_time,
                    error_message=f"Socket error code: {result}",
                    details={"connection_result": "failed", "socket_error_code": result}
                )
                
        except socket.timeout:
            response_time = int((time.time() - start_time) * 1000)
            return NetworkTest(
                test_name="tcp_connectivity",
                status=ConnectivityStatus.TIMEOUT,
                response_time_ms=response_time,
                error_message=f"Connection timed out after {self.timeout}s",
                details={"connection_result": "timeout"}
            )
        except socket.gaierror as e:
            response_time = int((time.time() - start_time) * 1000)
            return NetworkTest(
                test_name="tcp_connectivity",
                status=ConnectivityStatus.DNS_FAILURE,
                response_time_ms=response_time,
                error_message=f"DNS resolution failed: {str(e)}",
                details={"connection_result": "dns_failure", "dns_error": str(e)}
            )
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            return NetworkTest(
                test_name="tcp_connectivity",
                status=ConnectivityStatus.UNKNOWN_ERROR,
                response_time_ms=response_time,
                error_message=f"Unexpected error: {str(e)}",
                details={"connection_result": "error", "error_type": type(e).__name__}
            )
    
    async def test_dns_resolution(self, hostname: str) -> NetworkTest:
        """Test DNS resolution for a hostname."""
        start_time = time.time()
        
        try:
            # Resolve hostname to IP address
            ip_address = socket.gethostbyname(hostname)
            response_time = int((time.time() - start_time) * 1000)
            
            return NetworkTest(
                test_name="dns_resolution",
                status=ConnectivityStatus.SUCCESS,
                response_time_ms=response_time,
                error_message=None,
                details={"hostname": hostname, "resolved_ip": ip_address}
            )
            
        except socket.gaierror as e:
            response_time = int((time.time() - start_time) * 1000)
            return NetworkTest(
                test_name="dns_resolution",
                status=ConnectivityStatus.DNS_FAILURE,
                response_time_ms=response_time,
                error_message=f"DNS resolution failed: {str(e)}",
                details={"hostname": hostname, "dns_error": str(e)}
            )
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            return NetworkTest(
                test_name="dns_resolution",
                status=ConnectivityStatus.UNKNOWN_ERROR,
                response_time_ms=response_time,
                error_message=f"Unexpected error: {str(e)}",
                details={"hostname": hostname, "error_type": type(e).__name__}
            )
    
    async def test_postgresql_handshake(self, host: str, port: int) -> NetworkTest:
        """Test PostgreSQL protocol handshake."""
        start_time = time.time()
        
        try:
            # Create socket and attempt PostgreSQL startup message
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            # Connect to the server
            sock.connect((host, port))
            
            # Send PostgreSQL startup message
            # This is a simplified version - just testing if server responds
            startup_message = b'\x00\x00\x00\x08\x04\xd2\x16\x2f'
            sock.send(startup_message)
            
            # Try to receive response
            response = sock.recv(1024)
            response_time = int((time.time() - start_time) * 1000)
            
            sock.close()
            
            if response:
                return NetworkTest(
                    test_name="postgresql_handshake",
                    status=ConnectivityStatus.SUCCESS,
                    response_time_ms=response_time,
                    error_message=None,
                    details={"handshake_result": "success", "response_length": len(response)}
                )
            else:
                return NetworkTest(
                    test_name="postgresql_handshake",
                    status=ConnectivityStatus.CONNECTION_REFUSED,
                    response_time_ms=response_time,
                    error_message="No response from PostgreSQL server",
                    details={"handshake_result": "no_response"}
                )
                
        except socket.timeout:
            response_time = int((time.time() - start_time) * 1000)
            return NetworkTest(
                test_name="postgresql_handshake",
                status=ConnectivityStatus.TIMEOUT,
                response_time_ms=response_time,
                error_message=f"PostgreSQL handshake timed out after {self.timeout}s",
                details={"handshake_result": "timeout"}
            )
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            return NetworkTest(
                test_name="postgresql_handshake",
                status=ConnectivityStatus.UNKNOWN_ERROR,
                response_time_ms=response_time,
                error_message=f"PostgreSQL handshake failed: {str(e)}",
                details={"handshake_result": "error", "error_type": type(e).__name__}
            )
    
    def _generate_recommendations(self, tests: Dict[str, NetworkTest], host: str, port: int) -> list[str]:
        """Generate troubleshooting recommendations based on test results."""
        recommendations = []
        
        tcp_test = tests.get("tcp_connectivity")
        dns_test = tests.get("dns_resolution")
        pg_test = tests.get("postgresql_handshake")
        
        if dns_test and dns_test.status == ConnectivityStatus.DNS_FAILURE:
            recommendations.append("DNS resolution failed - check if hostname is correct or use IP address directly")
        
        if tcp_test and tcp_test.status == ConnectivityStatus.TIMEOUT:
            recommendations.extend([
                f"TCP connection to {host}:{port} timed out - this suggests network connectivity issues",
                "Check if the database server is running and accessible from Cloud Run",
                "Verify firewall rules allow connections from Cloud Run to the database",
                "Consider using Cloud SQL Proxy for secure connections",
                "If using private IP, ensure VPC connectivity is configured"
            ])
        
        if tcp_test and tcp_test.status == ConnectivityStatus.CONNECTION_REFUSED:
            recommendations.extend([
                f"Connection to {host}:{port} was refused - server may not be listening",
                "Verify PostgreSQL is running on the target server",
                "Check if PostgreSQL is configured to accept connections on the specified port",
                "Verify pg_hba.conf allows connections from Cloud Run IP ranges"
            ])
        
        if tcp_test and tcp_test.status == ConnectivityStatus.NETWORK_UNREACHABLE:
            recommendations.extend([
                f"Network route to {host} is unreachable from Cloud Run",
                "Check VPC configuration and routing rules",
                "Verify the database server is in an accessible network",
                "Consider using Cloud SQL or configuring VPC peering"
            ])
        
        if pg_test and pg_test.status != ConnectivityStatus.SUCCESS and tcp_test and tcp_test.status == ConnectivityStatus.SUCCESS:
            recommendations.extend([
                "TCP connection succeeded but PostgreSQL handshake failed",
                "Server may not be running PostgreSQL on this port",
                "Check if authentication is properly configured",
                "Verify PostgreSQL server configuration"
            ])
        
        if not recommendations:
            recommendations.append("All network tests passed - database connectivity should work")
        
        return recommendations
    
    async def generate_connectivity_report(self, host: str, port: int) -> ConnectivityReport:
        """Generate comprehensive connectivity report."""
        from datetime import datetime
        
        logger.info(f"Starting network diagnostics for {host}:{port}")
        
        # Run all network tests
        tests = {}
        
        # Test DNS resolution (if host is not an IP)
        try:
            socket.inet_aton(host)
            is_ip = True
        except socket.error:
            is_ip = False
        
        if not is_ip:
            tests["dns_resolution"] = await self.test_dns_resolution(host)
        
        # Test TCP connectivity
        tests["tcp_connectivity"] = await self.test_tcp_connectivity(host, port)
        
        # Test PostgreSQL handshake (only if TCP connection works)
        if tests["tcp_connectivity"].status == ConnectivityStatus.SUCCESS:
            tests["postgresql_handshake"] = await self.test_postgresql_handshake(host, port)
        
        # Determine overall status
        overall_status = ConnectivityStatus.SUCCESS
        for test in tests.values():
            if test.status != ConnectivityStatus.SUCCESS:
                overall_status = test.status
                break
        
        # Generate recommendations
        recommendations = self._generate_recommendations(tests, host, port)
        
        report = ConnectivityReport(
            target_host=host,
            target_port=port,
            overall_status=overall_status,
            tests=tests,
            recommendations=recommendations,
            timestamp=datetime.utcnow().isoformat()
        )
        
        logger.info(f"Network diagnostics completed. Overall status: {overall_status.value}")
        return report


async def test_database_connectivity(database_url: str) -> ConnectivityReport:
    """Test database connectivity and return detailed report."""
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(database_url)
        host = parsed.hostname
        port = parsed.port or 5432
        
        diagnostics = NetworkDiagnostics()
        return await diagnostics.generate_connectivity_report(host, port)
        
    except Exception as e:
        # Return error report if URL parsing fails
        return ConnectivityReport(
            target_host="unknown",
            target_port=0,
            overall_status=ConnectivityStatus.UNKNOWN_ERROR,
            tests={"url_parsing": NetworkTest(
                test_name="url_parsing",
                status=ConnectivityStatus.UNKNOWN_ERROR,
                response_time_ms=0,
                error_message=f"Failed to parse database URL: {str(e)}",
                details={"error_type": type(e).__name__}
            )},
            recommendations=[
                "Check database URL format",
                "Ensure URL follows format: postgresql://user:pass@host:port/db"
            ],
            timestamp=datetime.utcnow().isoformat()
        )