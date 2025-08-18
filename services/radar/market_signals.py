"""Market signals service for energy regulatory radar."""
import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import uuid

from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    """Market signal types."""
    TENDER = "tender"
    NOTICE = "notice"
    POLICY_UPDATE = "policy_update"
    MARKET_CHANGE = "market_change"
    REGULATORY_CHANGE = "regulatory_change"


class SignalPriority(str, Enum):
    """Signal priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Province(str, Enum):
    """Supported provinces."""
    GUANGDONG = "guangdong"
    SHANDONG = "shandong"
    INNER_MONGOLIA = "inner_mongolia"


class AssetType(str, Enum):
    """Asset types."""
    SOLAR = "solar"
    WIND = "wind"
    BATTERY = "battery"
    COAL_FLEXIBILITY = "coal_flexibility"


@dataclass
class MarketSignal:
    """Market signal data structure."""
    signal_id: str
    title: str
    title_en: str
    content: str
    content_en: str
    signal_type: str
    priority: str
    province: str
    asset_type: str
    source_url: str
    published_date: str
    effective_date: Optional[str]
    deadline_date: Optional[str]
    tags: List[str]
    impact_score: float
    relevance_score: float
    created_at: str
    updated_at: str


class MarketSignalFilter(BaseModel):
    """Market signal filter parameters."""
    provinces: Optional[List[Province]] = None
    asset_types: Optional[List[AssetType]] = None
    signal_types: Optional[List[SignalType]] = None
    priorities: Optional[List[SignalPriority]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    keywords: Optional[str] = None
    min_impact_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class MarketSignalsService:
    """Market signals service for radar functionality."""
    
    def __init__(self):
        """Initialize market signals service."""
        # In-memory storage for demo (would use BigQuery in production)
        self.signals: Dict[str, MarketSignal] = {}
        self.signal_stats = {
            "total_signals": 0,
            "by_type": {signal_type.value: 0 for signal_type in SignalType},
            "by_priority": {priority.value: 0 for priority in SignalPriority},
            "by_province": {province.value: 0 for province in Province},
            "by_asset_type": {asset_type.value: 0 for asset_type in AssetType}
        }
        
        # Initialize with sample data
        asyncio.create_task(self._initialize_sample_data())
    
    async def _initialize_sample_data(self):
        """Initialize with sample market signals."""
        try:
            sample_signals = [
                {
                    "title": "广东省2024年分布式光伏发电项目补贴申报通知",
                    "title_en": "Guangdong Province 2024 Distributed Solar PV Subsidy Application Notice",
                    "content": "根据《广东省可再生能源发展专项资金管理办法》，现启动2024年分布式光伏发电项目补贴申报工作。申报截止时间为2024年3月31日。",
                    "content_en": "According to the Guangdong Province Renewable Energy Development Special Fund Management Measures, the 2024 distributed solar PV project subsidy application is now open. Application deadline is March 31, 2024.",
                    "signal_type": SignalType.TENDER.value,
                    "priority": SignalPriority.HIGH.value,
                    "province": Province.GUANGDONG.value,
                    "asset_type": AssetType.SOLAR.value,
                    "source_url": "https://drc.gd.gov.cn/gkmlpt/content/3/3299/post_3299001.html",
                    "published_date": "2024-01-15",
                    "effective_date": "2024-01-15",
                    "deadline_date": "2024-03-31",
                    "tags": ["补贴", "申报", "分布式光伏", "subsidy", "application"],
                    "impact_score": 0.9,
                    "relevance_score": 0.95
                },
                {
                    "title": "山东省风电项目并网新规定发布",
                    "title_en": "Shandong Province New Wind Power Grid Connection Regulations Released",
                    "content": "山东省能源局发布《关于进一步规范风电项目并网管理的通知》，对风电项目并网流程、技术要求等进行了明确规定。",
                    "content_en": "Shandong Energy Bureau released the Notice on Further Standardizing Wind Power Project Grid Connection Management, clarifying grid connection procedures and technical requirements.",
                    "signal_type": SignalType.REGULATORY_CHANGE.value,
                    "priority": SignalPriority.MEDIUM.value,
                    "province": Province.SHANDONG.value,
                    "asset_type": AssetType.WIND.value,
                    "source_url": "https://nyj.shandong.gov.cn/art/2024/1/20/art_100476_234567.html",
                    "published_date": "2024-01-20",
                    "effective_date": "2024-02-01",
                    "deadline_date": None,
                    "tags": ["风电", "并网", "管理", "wind power", "grid connection"],
                    "impact_score": 0.7,
                    "relevance_score": 0.8
                },
                {
                    "title": "内蒙古储能项目建设招标公告",
                    "title_en": "Inner Mongolia Energy Storage Project Construction Tender Announcement",
                    "content": "内蒙古电力集团发布储能项目建设招标公告，计划建设100MW/200MWh储能项目，投标截止时间为2024年2月28日。",
                    "content_en": "Inner Mongolia Power Group announced tender for energy storage project construction, planning 100MW/200MWh storage project. Bid submission deadline is February 28, 2024.",
                    "signal_type": SignalType.TENDER.value,
                    "priority": SignalPriority.HIGH.value,
                    "province": Province.INNER_MONGOLIA.value,
                    "asset_type": AssetType.BATTERY.value,
                    "source_url": "https://impex.org.cn/art/2024/1/25/art_200125_345678.html",
                    "published_date": "2024-01-25",
                    "effective_date": "2024-01-25",
                    "deadline_date": "2024-02-28",
                    "tags": ["储能", "招标", "建设", "energy storage", "tender"],
                    "impact_score": 0.85,
                    "relevance_score": 0.9
                },
                {
                    "title": "广东省电力市场交易规则修订征求意见",
                    "title_en": "Guangdong Power Market Trading Rules Revision Public Consultation",
                    "content": "广东省发改委就《广东电力市场交易规则（修订版）》公开征求意见，意见反馈截止时间为2024年2月15日。",
                    "content_en": "Guangdong Development and Reform Commission seeks public comments on the revised Guangdong Power Market Trading Rules. Comment deadline is February 15, 2024.",
                    "signal_type": SignalType.POLICY_UPDATE.value,
                    "priority": SignalPriority.MEDIUM.value,
                    "province": Province.GUANGDONG.value,
                    "asset_type": AssetType.SOLAR.value,
                    "source_url": "https://drc.gd.gov.cn/gkmlpt/content/3/3300/post_3300123.html",
                    "published_date": "2024-01-30",
                    "effective_date": "2024-01-30",
                    "deadline_date": "2024-02-15",
                    "tags": ["电力市场", "交易规则", "征求意见", "power market", "trading rules"],
                    "impact_score": 0.75,
                    "relevance_score": 0.85
                },
                {
                    "title": "山东省煤电灵活性改造项目补贴政策",
                    "title_en": "Shandong Province Coal Power Flexibility Retrofit Subsidy Policy",
                    "content": "山东省能源局发布煤电灵活性改造项目补贴政策，对完成改造的机组给予每千瓦200元的一次性补贴。",
                    "content_en": "Shandong Energy Bureau released subsidy policy for coal power flexibility retrofit projects, providing one-time subsidy of 200 yuan per kW for completed retrofits.",
                    "signal_type": SignalType.POLICY_UPDATE.value,
                    "priority": SignalPriority.MEDIUM.value,
                    "province": Province.SHANDONG.value,
                    "asset_type": AssetType.COAL_FLEXIBILITY.value,
                    "source_url": "https://nyj.shandong.gov.cn/art/2024/2/1/art_100477_345678.html",
                    "published_date": "2024-02-01",
                    "effective_date": "2024-02-01",
                    "deadline_date": None,
                    "tags": ["煤电", "灵活性改造", "补贴", "coal power", "flexibility"],
                    "impact_score": 0.6,
                    "relevance_score": 0.7
                }
            ]
            
            for i, signal_data in enumerate(sample_signals, 1):
                signal_id = f"SIG-{datetime.utcnow().strftime('%Y%m%d')}-{i:03d}"
                
                signal = MarketSignal(
                    signal_id=signal_id,
                    title=signal_data["title"],
                    title_en=signal_data["title_en"],
                    content=signal_data["content"],
                    content_en=signal_data["content_en"],
                    signal_type=signal_data["signal_type"],
                    priority=signal_data["priority"],
                    province=signal_data["province"],
                    asset_type=signal_data["asset_type"],
                    source_url=signal_data["source_url"],
                    published_date=signal_data["published_date"],
                    effective_date=signal_data["effective_date"],
                    deadline_date=signal_data["deadline_date"],
                    tags=signal_data["tags"],
                    impact_score=signal_data["impact_score"],
                    relevance_score=signal_data["relevance_score"],
                    created_at=datetime.utcnow().isoformat(),
                    updated_at=datetime.utcnow().isoformat()
                )
                
                self.signals[signal_id] = signal
                self._update_stats(signal)
            
            logger.info(f"Initialized {len(sample_signals)} sample market signals")
            
        except Exception as e:
            logger.error(f"Failed to initialize sample data: {e}")
    
    async def get_signals(self, filters: MarketSignalFilter) -> Dict[str, Any]:
        """Get market signals with filtering."""
        try:
            # Start with all signals
            filtered_signals = list(self.signals.values())
            
            # Apply filters
            if filters.provinces:
                province_values = [p.value for p in filters.provinces]
                filtered_signals = [s for s in filtered_signals if s.province in province_values]
            
            if filters.asset_types:
                asset_values = [a.value for a in filters.asset_types]
                filtered_signals = [s for s in filtered_signals if s.asset_type in asset_values]
            
            if filters.signal_types:
                type_values = [t.value for t in filters.signal_types]
                filtered_signals = [s for s in filtered_signals if s.signal_type in type_values]
            
            if filters.priorities:
                priority_values = [p.value for p in filters.priorities]
                filtered_signals = [s for s in filtered_signals if s.priority in priority_values]
            
            if filters.date_from:
                filtered_signals = [s for s in filtered_signals if s.published_date >= filters.date_from]
            
            if filters.date_to:
                filtered_signals = [s for s in filtered_signals if s.published_date <= filters.date_to]
            
            if filters.keywords:
                keywords = filters.keywords.lower()
                filtered_signals = [
                    s for s in filtered_signals 
                    if keywords in s.title.lower() or keywords in s.content.lower() or
                       any(keywords in tag.lower() for tag in s.tags)
                ]
            
            if filters.min_impact_score is not None:
                filtered_signals = [s for s in filtered_signals if s.impact_score >= filters.min_impact_score]
            
            # Sort by relevance score and published date
            filtered_signals.sort(key=lambda s: (s.relevance_score, s.published_date), reverse=True)
            
            # Apply pagination
            total_count = len(filtered_signals)
            paginated_signals = filtered_signals[filters.offset:filters.offset + filters.limit]
            
            return {
                "signals": [asdict(signal) for signal in paginated_signals],
                "total_count": total_count,
                "returned_count": len(paginated_signals),
                "filters": filters.dict(),
                "retrieved_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get signals: {e}")
            raise
    
    async def get_signal_by_id(self, signal_id: str) -> Optional[MarketSignal]:
        """Get specific signal by ID."""
        return self.signals.get(signal_id)
    
    async def get_signal_stats(self) -> Dict[str, Any]:
        """Get signal statistics."""
        try:
            # Calculate real-time stats
            total_signals = len(self.signals)
            
            # Type distribution
            type_counts = {}
            for signal in self.signals.values():
                type_counts[signal.signal_type] = type_counts.get(signal.signal_type, 0) + 1
            
            # Priority distribution
            priority_counts = {}
            for signal in self.signals.values():
                priority_counts[signal.priority] = priority_counts.get(signal.priority, 0) + 1
            
            # Province distribution
            province_counts = {}
            for signal in self.signals.values():
                province_counts[signal.province] = province_counts.get(signal.province, 0) + 1
            
            # Asset type distribution
            asset_counts = {}
            for signal in self.signals.values():
                asset_counts[signal.asset_type] = asset_counts.get(signal.asset_type, 0) + 1
            
            # Recent activity (last 30 days)
            thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
            recent_signals = [
                s for s in self.signals.values() 
                if s.published_date >= thirty_days_ago
            ]
            
            # Upcoming deadlines (next 30 days)
            thirty_days_later = (datetime.utcnow() + timedelta(days=30)).strftime('%Y-%m-%d')
            upcoming_deadlines = [
                s for s in self.signals.values() 
                if s.deadline_date and s.deadline_date <= thirty_days_later
            ]
            
            return {
                "total_signals": total_signals,
                "type_distribution": type_counts,
                "priority_distribution": priority_counts,
                "province_distribution": province_counts,
                "asset_type_distribution": asset_counts,
                "recent_activity": {
                    "count": len(recent_signals),
                    "period": "last_30_days"
                },
                "upcoming_deadlines": {
                    "count": len(upcoming_deadlines),
                    "period": "next_30_days",
                    "signals": [
                        {
                            "signal_id": s.signal_id,
                            "title": s.title,
                            "deadline_date": s.deadline_date,
                            "priority": s.priority
                        } for s in sorted(upcoming_deadlines, key=lambda x: x.deadline_date)[:5]
                    ]
                },
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get signal stats: {e}")
            return {}
    
    async def export_signals_csv(self, filters: MarketSignalFilter) -> str:
        """Export filtered signals to CSV format."""
        try:
            import csv
            import io
            
            # Get filtered signals
            result = await self.get_signals(filters)
            signals = result["signals"]
            
            # Create CSV content
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            header = [
                "Signal ID", "Title", "Title (EN)", "Content", "Content (EN)",
                "Type", "Priority", "Province", "Asset Type", "Source URL",
                "Published Date", "Effective Date", "Deadline Date", "Tags",
                "Impact Score", "Relevance Score", "Created At", "Updated At"
            ]
            writer.writerow(header)
            
            # Write data rows
            for signal in signals:
                row = [
                    signal["signal_id"],
                    signal["title"],
                    signal["title_en"],
                    signal["content"],
                    signal["content_en"],
                    signal["signal_type"],
                    signal["priority"],
                    signal["province"],
                    signal["asset_type"],
                    signal["source_url"],
                    signal["published_date"],
                    signal["effective_date"] or "",
                    signal["deadline_date"] or "",
                    ", ".join(signal["tags"]),
                    signal["impact_score"],
                    signal["relevance_score"],
                    signal["created_at"],
                    signal["updated_at"]
                ]
                writer.writerow(row)
            
            csv_content = output.getvalue()
            output.close()
            
            logger.info(f"Exported {len(signals)} signals to CSV")
            return csv_content
            
        except Exception as e:
            logger.error(f"Failed to export signals to CSV: {e}")
            raise
    
    def _update_stats(self, signal: MarketSignal):
        """Update signal statistics."""
        self.signal_stats["total_signals"] += 1
        self.signal_stats["by_type"][signal.signal_type] += 1
        self.signal_stats["by_priority"][signal.priority] += 1
        self.signal_stats["by_province"][signal.province] += 1
        self.signal_stats["by_asset_type"][signal.asset_type] += 1


# Global service instance
_market_signals_service = None


async def get_market_signals_service() -> MarketSignalsService:
    """Get or create global market signals service instance."""
    global _market_signals_service
    
    if _market_signals_service is None:
        _market_signals_service = MarketSignalsService()
    
    return _market_signals_service