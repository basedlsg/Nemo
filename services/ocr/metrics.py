"""Metrics collection and logging for OCR service."""

import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque

from .schemas import OcrResult, OcrStatus, OcrMetrics

logger = logging.getLogger(__name__)


class OcrMetricsCollector:
    """Collects and aggregates OCR service metrics."""
    
    def __init__(self, max_recent_jobs: int = 1000):
        """Initialize metrics collector."""
        self.max_recent_jobs = max_recent_jobs
        self.recent_jobs = deque(maxlen=max_recent_jobs)
        self.metrics = OcrMetrics()
        self.start_time = datetime.utcnow()
        
        logger.info("Initialized OCR metrics collector")
    
    def record_job_result(self, result: OcrResult) -> None:
        """Record the result of an OCR job."""
        try:
            # Add to recent jobs
            self.recent_jobs.append({
                "job_id": str(result.job_id),
                "status": result.status.value,
                "processing_time_ms": result.processing_time_ms,
                "pages_processed": result.pages_processed,
                "tables_extracted": result.tables_extracted,
                "effective_date_found": result.effective_date_found,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Update aggregate metrics
            self.metrics.update_with_result(result)
            
            # Log structured metrics
            self._log_job_metrics(result)
            
        except Exception as e:
            logger.error(f"Error recording job result: {e}")
    
    def record_processing_latency(self, operation: str, latency_ms: int) -> None:
        """Record latency for specific operations."""
        try:
            # Log structured latency
            logger.info(
                "OCR operation latency",
                extra={
                    "operation": operation,
                    "latency_ms": latency_ms,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error recording latency: {e}")
    
    def record_error(self, error_type: str, error_message: str, job_id: Optional[str] = None) -> None:
        """Record an error occurrence."""
        try:
            logger.error(
                "OCR processing error",
                extra={
                    "error_type": error_type,
                    "error_message": error_message,
                    "job_id": job_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error recording error: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics summary."""
        try:
            # Calculate additional metrics from recent jobs
            recent_metrics = self._calculate_recent_metrics()
            
            # Combine with aggregate metrics
            metrics_dict = self.metrics.dict()
            metrics_dict.update(recent_metrics)
            
            # Add service metadata
            metrics_dict["service_uptime_seconds"] = (
                datetime.utcnow() - self.start_time
            ).total_seconds()
            
            metrics_dict["recent_jobs_count"] = len(self.recent_jobs)
            
            return metrics_dict
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {"error": str(e)}
    
    def get_slo_metrics(self) -> Dict[str, Any]:
        """Get SLO-specific metrics."""
        try:
            metrics = self.get_metrics()
            
            # Calculate SLO metrics
            slo_metrics = {
                "success_rate": metrics.get("success_rate", 0.0),
                "effective_date_hit_rate": metrics.get("effective_date_hit_rate", 0.0),
                "avg_processing_time_ms": metrics.get("avg_processing_time_ms", 0.0),
                "p95_processing_time_ms": self._calculate_p95_latency(),
                "tables_per_job": metrics.get("tables_per_job", 0.0),
                "pages_per_job": metrics.get("avg_pages_per_job", 0.0)
            }
            
            # SLO targets
            slo_targets = {
                "success_rate_target": 0.95,
                "effective_date_hit_rate_target": 0.80,
                "p95_processing_time_target_ms": 12000,  # 12 seconds
                "min_tables_per_job": 0.1
            }
            
            # Calculate SLO compliance
            slo_compliance = {}
            for metric, value in slo_metrics.items():
                target_key = f"{metric}_target"
                if target_key in slo_targets:
                    target = slo_targets[target_key]
                    if "time" in metric:
                        # Lower is better for latency
                        slo_compliance[metric] = value <= target
                    else:
                        # Higher is better for rates
                        slo_compliance[metric] = value >= target
            
            return {
                "metrics": slo_metrics,
                "targets": slo_targets,
                "compliance": slo_compliance,
                "overall_slo_met": all(slo_compliance.values())
            }
            
        except Exception as e:
            logger.error(f"Error calculating SLO metrics: {e}")
            return {"error": str(e)}
    
    def _calculate_recent_metrics(self) -> Dict[str, Any]:
        """Calculate metrics from recent jobs."""
        if not self.recent_jobs:
            return {}
        
        # Convert to list for easier processing
        jobs = list(self.recent_jobs)
        
        # Calculate distributions
        status_counts = defaultdict(int)
        processing_times = []
        pages_counts = []
        tables_counts = []
        effective_dates_found = 0
        
        for job in jobs:
            status_counts[job["status"]] += 1
            
            if job["processing_time_ms"]:
                processing_times.append(job["processing_time_ms"])
            
            if job["pages_processed"]:
                pages_counts.append(job["pages_processed"])
            
            if job["tables_extracted"]:
                tables_counts.append(job["tables_extracted"])
            
            if job["effective_date_found"]:
                effective_dates_found += 1
        
        # Calculate percentiles
        recent_metrics = {
            "recent_jobs_status_distribution": dict(status_counts),
            "recent_success_rate": status_counts["success"] / len(jobs) if jobs else 0.0,
            "recent_effective_date_hit_rate": effective_dates_found / len(jobs) if jobs else 0.0
        }
        
        if processing_times:
            processing_times.sort()
            recent_metrics.update({
                "recent_p50_processing_time_ms": self._percentile(processing_times, 50),
                "recent_p95_processing_time_ms": self._percentile(processing_times, 95),
                "recent_p99_processing_time_ms": self._percentile(processing_times, 99)
            })
        
        if pages_counts:
            recent_metrics["recent_avg_pages_per_job"] = sum(pages_counts) / len(pages_counts)
        
        if tables_counts:
            recent_metrics["recent_avg_tables_per_job"] = sum(tables_counts) / len(tables_counts)
        
        return recent_metrics
    
    def _calculate_p95_latency(self) -> float:
        """Calculate P95 processing latency from recent jobs."""
        processing_times = [
            job["processing_time_ms"] 
            for job in self.recent_jobs 
            if job["processing_time_ms"]
        ]
        
        if not processing_times:
            return 0.0
        
        processing_times.sort()
        return self._percentile(processing_times, 95)
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile from sorted data."""
        if not data:
            return 0.0
        
        index = (percentile / 100.0) * (len(data) - 1)
        
        if index.is_integer():
            return data[int(index)]
        else:
            lower = data[int(index)]
            upper = data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    def _log_job_metrics(self, result: OcrResult) -> None:
        """Log structured metrics for a job."""
        try:
            # Create structured log entry
            log_data = {
                "service": "ocr",
                "job_id": str(result.job_id),
                "status": result.status.value,
                "processing_time_ms": result.processing_time_ms,
                "pages_processed": result.pages_processed,
                "tables_extracted": result.tables_extracted,
                "effective_date_found": result.effective_date_found,
                "verdict": "success" if result.is_success() else "failed",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if result.error_message:
                log_data["error_message"] = result.error_message
            
            if result.citation_id:
                log_data["citation_id"] = str(result.citation_id)
            
            # Log with appropriate level
            if result.is_success():
                logger.info("OCR job completed", extra=log_data)
            else:
                logger.error("OCR job failed", extra=log_data)
                
        except Exception as e:
            logger.error(f"Error logging job metrics: {e}")
    
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        try:
            metrics = self.get_metrics()
            prometheus_lines = []
            
            # Add help and type information
            prometheus_lines.extend([
                "# HELP ocr_jobs_total Total number of OCR jobs processed",
                "# TYPE ocr_jobs_total counter",
                f"ocr_jobs_total {metrics.get('total_jobs', 0)}",
                "",
                "# HELP ocr_jobs_successful_total Total number of successful OCR jobs",
                "# TYPE ocr_jobs_successful_total counter", 
                f"ocr_jobs_successful_total {metrics.get('successful_jobs', 0)}",
                "",
                "# HELP ocr_processing_time_ms_avg Average processing time in milliseconds",
                "# TYPE ocr_processing_time_ms_avg gauge",
                f"ocr_processing_time_ms_avg {metrics.get('avg_processing_time_ms', 0)}",
                "",
                "# HELP ocr_pages_processed_total Total number of pages processed",
                "# TYPE ocr_pages_processed_total counter",
                f"ocr_pages_processed_total {metrics.get('total_pages_processed', 0)}",
                "",
                "# HELP ocr_tables_extracted_total Total number of tables extracted",
                "# TYPE ocr_tables_extracted_total counter",
                f"ocr_tables_extracted_total {metrics.get('total_tables_extracted', 0)}",
                "",
                "# HELP ocr_effective_dates_found_total Total number of effective dates found",
                "# TYPE ocr_effective_dates_found_total counter",
                f"ocr_effective_dates_found_total {metrics.get('effective_dates_found', 0)}",
                ""
            ])
            
            return "\n".join(prometheus_lines)
            
        except Exception as e:
            logger.error(f"Error exporting Prometheus metrics: {e}")
            return f"# Error exporting metrics: {e}\n"
    
    def reset_metrics(self) -> None:
        """Reset all metrics (for testing)."""
        self.recent_jobs.clear()
        self.metrics = OcrMetrics()
        self.start_time = datetime.utcnow()
        logger.info("OCR metrics reset")


class StructuredLogger:
    """Structured logger for OCR service."""
    
    def __init__(self, service_name: str = "ocr"):
        self.service_name = service_name
        self.logger = logging.getLogger(f"services.{service_name}")
    
    def log_job_start(self, job_id: str, gcs_uri: str, province: str, doc_class: str) -> None:
        """Log job start."""
        self.logger.info(
            "OCR job started",
            extra={
                "service": self.service_name,
                "event": "job_start",
                "job_id": job_id,
                "gcs_uri": gcs_uri,
                "province": province,
                "doc_class": doc_class,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def log_job_complete(
        self, 
        job_id: str, 
        status: str, 
        processing_time_ms: int,
        citation_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Log job completion."""
        log_data = {
            "service": self.service_name,
            "event": "job_complete",
            "job_id": job_id,
            "status": status,
            "processing_time_ms": processing_time_ms,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if citation_id:
            log_data["citation_id"] = citation_id
        
        if error_message:
            log_data["error_message"] = error_message
        
        if status == "success":
            self.logger.info("OCR job completed successfully", extra=log_data)
        else:
            self.logger.error("OCR job failed", extra=log_data)
    
    def log_processing_step(
        self, 
        job_id: str, 
        step: str, 
        duration_ms: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log processing step."""
        log_data = {
            "service": self.service_name,
            "event": "processing_step",
            "job_id": job_id,
            "step": step,
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if metadata:
            log_data.update(metadata)
        
        self.logger.info(f"OCR step completed: {step}", extra=log_data)