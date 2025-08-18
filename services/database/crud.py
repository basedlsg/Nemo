"""CRUD operations for database models."""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Citation, Pack, Source, EvaluationMetric, QueryLog, IngestionJob
from .models import CitationCreate, SourceCreate, QueryLogCreate


class CitationCRUD:
    """CRUD operations for citations."""
    
    @staticmethod
    async def create(session: AsyncSession, citation_data: CitationCreate) -> Citation:
        """Create a new citation."""
        citation = Citation(**citation_data.dict())
        session.add(citation)
        await session.commit()
        await session.refresh(citation)
        return citation
    
    @staticmethod
    async def get_by_id(session: AsyncSession, citation_id: UUID) -> Optional[Citation]:
        """Get citation by ID."""
        result = await session.execute(
            select(Citation).where(Citation.citation_id == citation_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_checksum(session: AsyncSession, checksum: str) -> Optional[Citation]:
        """Get citation by checksum to avoid duplicates."""
        result = await session.execute(
            select(Citation).where(Citation.checksum == checksum)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_active_by_province_and_class(
        session: AsyncSession,
        province: str,
        doc_class: str,
        asset: Optional[str] = None,
        limit: int = 100
    ) -> List[Citation]:
        """Get active (non-superseded) citations by province and document class."""
        query = select(Citation).where(
            and_(
                Citation.province == province,
                Citation.doc_class == doc_class,
                Citation.superseded_by.is_(None)
            )
        )
        
        if asset:
            query = query.where(Citation.asset == asset)
            
        query = query.order_by(Citation.effective_date.desc()).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def mark_superseded(
        session: AsyncSession,
        old_citation_id: UUID,
        new_citation_id: UUID
    ) -> bool:
        """Mark a citation as superseded by a newer one."""
        result = await session.execute(
            update(Citation)
            .where(Citation.citation_id == old_citation_id)
            .values(superseded_by=new_citation_id)
        )
        await session.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def search_by_content(
        session: AsyncSession,
        search_text: str,
        province: str,
        doc_class: str,
        limit: int = 10
    ) -> List[Citation]:
        """Full-text search in citation content."""
        query = select(Citation).where(
            and_(
                Citation.province == province,
                Citation.doc_class == doc_class,
                Citation.superseded_by.is_(None),
                Citation.content.ilike(f"%{search_text}%")
            )
        ).order_by(Citation.effective_date.desc()).limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()


class PackCRUD:
    """CRUD operations for packs."""
    
    @staticmethod
    async def create(
        session: AsyncSession,
        province: str,
        asset: Optional[str],
        doc_class: str,
        query_fingerprint: str,
        citation_ids: List[UUID],
        answer_zh: Optional[str] = None
    ) -> Pack:
        """Create a new pack."""
        pack = Pack(
            province=province,
            asset=asset,
            doc_class=doc_class,
            query_fingerprint=query_fingerprint,
            citation_ids=citation_ids,
            answer_zh=answer_zh
        )
        session.add(pack)
        await session.commit()
        await session.refresh(pack)
        return pack
    
    @staticmethod
    async def get_by_id(session: AsyncSession, pack_id: UUID) -> Optional[Pack]:
        """Get pack by ID."""
        result = await session.execute(
            select(Pack).where(Pack.pack_id == pack_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_query_fingerprint(
        session: AsyncSession,
        query_fingerprint: str,
        max_age_hours: int = 24
    ) -> Optional[Pack]:
        """Get recent pack by query fingerprint for caching."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        result = await session.execute(
            select(Pack).where(
                and_(
                    Pack.query_fingerprint == query_fingerprint,
                    Pack.created_at >= cutoff_time,
                    Pack.pack_status == "generated"
                )
            ).order_by(Pack.created_at.desc())
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_status(
        session: AsyncSession,
        pack_id: UUID,
        status: str
    ) -> bool:
        """Update pack status."""
        result = await session.execute(
            update(Pack)
            .where(Pack.pack_id == pack_id)
            .values(pack_status=status)
        )
        await session.commit()
        return result.rowcount > 0


class SourceCRUD:
    """CRUD operations for sources."""
    
    @staticmethod
    async def create(session: AsyncSession, source_data: SourceCreate) -> Source:
        """Create a new source."""
        source = Source(**source_data.dict())
        session.add(source)
        await session.commit()
        await session.refresh(source)
        return source
    
    @staticmethod
    async def get_by_domain(session: AsyncSession, domain: str) -> Optional[Source]:
        """Get source by domain."""
        result = await session.execute(
            select(Source).where(Source.domain == domain)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_enabled_by_province(
        session: AsyncSession,
        province: str
    ) -> List[Source]:
        """Get enabled sources for a province."""
        result = await session.execute(
            select(Source).where(
                and_(
                    Source.province == province,
                    Source.enabled == True
                )
            )
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_stale_sources(
        session: AsyncSession,
        hours_threshold: int = 48
    ) -> List[Source]:
        """Get sources that haven't been crawled recently."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_threshold)
        
        result = await session.execute(
            select(Source).where(
                and_(
                    Source.enabled == True,
                    or_(
                        Source.last_crawled_at.is_(None),
                        Source.last_crawled_at < cutoff_time
                    )
                )
            )
        )
        return result.scalars().all()
    
    @staticmethod
    async def update_crawl_time(
        session: AsyncSession,
        domain: str,
        crawl_time: Optional[datetime] = None
    ) -> bool:
        """Update last crawled time for a source."""
        if crawl_time is None:
            crawl_time = datetime.utcnow()
            
        result = await session.execute(
            update(Source)
            .where(Source.domain == domain)
            .values(last_crawled_at=crawl_time)
        )
        await session.commit()
        return result.rowcount > 0


class EvaluationMetricCRUD:
    """CRUD operations for evaluation metrics."""
    
    @staticmethod
    async def create_or_update(
        session: AsyncSession,
        province: str,
        doc_class: str,
        evaluation_date: date,
        **metrics
    ) -> EvaluationMetric:
        """Create or update evaluation metrics for a province/doc_class/date."""
        # Try to find existing metric
        result = await session.execute(
            select(EvaluationMetric).where(
                and_(
                    EvaluationMetric.province == province,
                    EvaluationMetric.doc_class == doc_class,
                    EvaluationMetric.evaluation_date == evaluation_date
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing
            for key, value in metrics.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await session.commit()
            await session.refresh(existing)
            return existing
        else:
            # Create new
            metric = EvaluationMetric(
                province=province,
                doc_class=doc_class,
                evaluation_date=evaluation_date,
                **metrics
            )
            session.add(metric)
            await session.commit()
            await session.refresh(metric)
            return metric
    
    @staticmethod
    async def get_latest_by_province(
        session: AsyncSession,
        province: str,
        doc_class: Optional[str] = None
    ) -> List[EvaluationMetric]:
        """Get latest evaluation metrics for a province."""
        query = select(EvaluationMetric).where(
            EvaluationMetric.province == province
        )
        
        if doc_class:
            query = query.where(EvaluationMetric.doc_class == doc_class)
            
        query = query.order_by(EvaluationMetric.evaluation_date.desc()).limit(10)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def check_province_readiness(
        session: AsyncSession,
        province: str,
        doc_class: str,
        min_groundedness: float = 0.9,
        min_citation_precision: float = 0.95,
        min_refusal_accuracy: float = 0.99
    ) -> bool:
        """Check if province/doc_class meets quality thresholds."""
        result = await session.execute(
            select(EvaluationMetric).where(
                and_(
                    EvaluationMetric.province == province,
                    EvaluationMetric.doc_class == doc_class
                )
            ).order_by(EvaluationMetric.evaluation_date.desc()).limit(1)
        )
        
        latest = result.scalar_one_or_none()
        if not latest:
            return False
            
        return (
            (latest.groundedness_score or 0) >= min_groundedness and
            (latest.citation_precision or 0) >= min_citation_precision and
            (latest.refusal_accuracy or 0) >= min_refusal_accuracy
        )


class QueryLogCRUD:
    """CRUD operations for query logs."""
    
    @staticmethod
    async def create(session: AsyncSession, log_data: QueryLogCreate) -> QueryLog:
        """Create a new query log entry."""
        log_entry = QueryLog(**log_data.dict())
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)
        return log_entry
    
    @staticmethod
    async def get_by_trace_id(
        session: AsyncSession,
        trace_id: str
    ) -> List[QueryLog]:
        """Get all log entries for a trace ID."""
        result = await session.execute(
            select(QueryLog).where(QueryLog.trace_id == trace_id)
            .order_by(QueryLog.created_at)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_recent_stats(
        session: AsyncSession,
        hours: int = 24,
        province: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get recent query statistics."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = select(QueryLog).where(QueryLog.created_at >= cutoff_time)
        if province:
            query = query.where(QueryLog.province == province)
            
        result = await session.execute(query)
        logs = result.scalars().all()
        
        total_queries = len(logs)
        if total_queries == 0:
            return {"total_queries": 0}
            
        ok_queries = sum(1 for log in logs if log.verdict == "ok")
        refused_queries = sum(1 for log in logs if log.verdict == "refused")
        error_queries = sum(1 for log in logs if log.verdict == "error")
        
        latencies = [log.latency_ms for log in logs if log.latency_ms is not None]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        return {
            "total_queries": total_queries,
            "ok_queries": ok_queries,
            "refused_queries": refused_queries,
            "error_queries": error_queries,
            "refusal_rate": refused_queries / total_queries,
            "error_rate": error_queries / total_queries,
            "avg_latency_ms": avg_latency,
        }


class IngestionJobCRUD:
    """CRUD operations for ingestion jobs."""
    
    @staticmethod
    async def create(
        session: AsyncSession,
        source_domain: str,
        url: str,
        job_type: str = "discovery"
    ) -> IngestionJob:
        """Create a new ingestion job."""
        job = IngestionJob(
            source_domain=source_domain,
            url=url,
            job_type=job_type
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job
    
    @staticmethod
    async def get_pending_jobs(
        session: AsyncSession,
        job_type: Optional[str] = None,
        limit: int = 100
    ) -> List[IngestionJob]:
        """Get pending ingestion jobs."""
        query = select(IngestionJob).where(
            IngestionJob.job_status == "pending"
        ).order_by(IngestionJob.scheduled_at)
        
        if job_type:
            query = query.where(IngestionJob.job_type == job_type)
            
        query = query.limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def update_job_status(
        session: AsyncSession,
        job_id: UUID,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """Update job status and optionally error message."""
        update_data = {"job_status": status}
        
        if status == "processing":
            update_data["started_at"] = datetime.utcnow()
        elif status in ("completed", "failed"):
            update_data["completed_at"] = datetime.utcnow()
            
        if error_message:
            update_data["error_message"] = error_message
            
        result = await session.execute(
            update(IngestionJob)
            .where(IngestionJob.job_id == job_id)
            .values(**update_data)
        )
        await session.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def retry_failed_jobs(
        session: AsyncSession,
        max_age_hours: int = 24
    ) -> List[IngestionJob]:
        """Get failed jobs that can be retried."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        result = await session.execute(
            select(IngestionJob).where(
                and_(
                    IngestionJob.job_status == "failed",
                    IngestionJob.retry_count < IngestionJob.max_retries,
                    IngestionJob.completed_at >= cutoff_time
                )
            )
        )
        
        jobs = result.scalars().all()
        
        # Update jobs to retrying status
        for job in jobs:
            job.job_status = "retrying"
            job.retry_count += 1
            
        await session.commit()
        return jobs