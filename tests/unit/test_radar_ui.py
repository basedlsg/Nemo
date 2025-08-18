"""Tests for Radar UI components and market signals functionality."""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from services.radar.api import app
from services.radar.market_signals import (
    MarketSignalsService,
    MarketSignalFilter,
    SignalType,
    SignalPriority,
    Province,
    AssetType
)


class TestRadarAPI:
    """Test Radar API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Test client fixture."""
        return TestClient(app)
    
    @pytest.fixture
    def sample_signals_response(self):
        """Sample signals response for testing."""
        return {
            "signals": [
                {
                    "signal_id": "SIG-20240116-001",
                    "title": "广东省2024年分布式光伏发电项目补贴申报通知",
                    "title_en": "Guangdong Province 2024 Distributed Solar PV Subsidy Application Notice",
                    "content": "根据《广东省可再生能源发展专项资金管理办法》，现启动2024年分布式光伏发电项目补贴申报工作。",
                    "content_en": "According to the Guangdong Province Renewable Energy Development Special Fund Management Measures, the 2024 distributed solar PV project subsidy application is now open.",
                    "signal_type": "tender",
                    "priority": "high",
                    "province": "guangdong",
                    "asset_type": "solar",
                    "source_url": "https://drc.gd.gov.cn/test.html",
                    "published_date": "2024-01-15",
                    "effective_date": "2024-01-15",
                    "deadline_date": "2024-03-31",
                    "tags": ["补贴", "申报", "分布式光伏"],
                    "impact_score": 0.9,
                    "relevance_score": 0.95,
                    "created_at": "2024-01-16T10:00:00",
                    "updated_at": "2024-01-16T10:00:00"
                }
            ],
            "total_count": 1,
            "returned_count": 1,
            "filters": {},
            "retrieved_at": "2024-01-16T10:00:00"
        }
    
    def test_get_signals_no_filters(self, client):
        """Test getting signals without filters."""
        with patch('services.radar.api.get_market_signals_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_signals.return_value = {
                "signals": [],
                "total_count": 0,
                "returned_count": 0,
                "filters": {},
                "retrieved_at": datetime.utcnow().isoformat()
            }
            mock_get_service.return_value = mock_service
            
            response = client.get("/signals")
            assert response.status_code == 200
            
            data = response.json()
            assert "signals" in data
            assert "total_count" in data
            assert data["total_count"] == 0
    
    def test_get_signals_with_filters(self, client, sample_signals_response):
        """Test getting signals with filters."""
        with patch('services.radar.api.get_market_signals_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_signals.return_value = sample_signals_response
            mock_get_service.return_value = mock_service
            
            response = client.get("/signals?provinces=guangdong&asset_types=solar&priorities=high")
            assert response.status_code == 200
            
            data = response.json()
            assert data["total_count"] == 1
            assert len(data["signals"]) == 1
            assert data["signals"][0]["province"] == "guangdong"
            assert data["signals"][0]["asset_type"] == "solar"
            assert data["signals"][0]["priority"] == "high"
    
    def test_get_signals_invalid_province(self, client):
        """Test getting signals with invalid province."""
        response = client.get("/signals?provinces=invalid_province")
        assert response.status_code == 400
        assert "Invalid province" in response.json()["detail"]
    
    def test_get_signals_invalid_asset_type(self, client):
        """Test getting signals with invalid asset type."""
        response = client.get("/signals?asset_types=invalid_asset")
        assert response.status_code == 400
        assert "Invalid asset type" in response.json()["detail"]
    
    def test_get_signals_pagination(self, client):
        """Test signals pagination."""
        with patch('services.radar.api.get_market_signals_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_signals.return_value = {
                "signals": [],
                "total_count": 100,
                "returned_count": 20,
                "filters": {"limit": 20, "offset": 40},
                "retrieved_at": datetime.utcnow().isoformat()
            }
            mock_get_service.return_value = mock_service
            
            response = client.get("/signals?limit=20&offset=40")
            assert response.status_code == 200
            
            data = response.json()
            assert data["total_count"] == 100
            assert data["returned_count"] == 20
            assert data["filters"]["limit"] == 20
            assert data["filters"]["offset"] == 40
    
    def test_get_signal_by_id(self, client):
        """Test getting specific signal by ID."""
        with patch('services.radar.api.get_market_signals_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_signal = Mock()
            mock_signal.__dict__ = {
                "signal_id": "SIG-20240116-001",
                "title": "Test Signal",
                "priority": "high"
            }
            mock_service.get_signal_by_id.return_value = mock_signal
            mock_get_service.return_value = mock_service
            
            response = client.get("/signals/SIG-20240116-001")
            assert response.status_code == 200
            
            data = response.json()
            assert data["signal"]["signal_id"] == "SIG-20240116-001"
            assert data["signal"]["title"] == "Test Signal"
    
    def test_get_signal_not_found(self, client):
        """Test getting non-existent signal."""
        with patch('services.radar.api.get_market_signals_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_signal_by_id.return_value = None
            mock_get_service.return_value = mock_service
            
            response = client.get("/signals/nonexistent")
            assert response.status_code == 404
            assert "Signal not found" in response.json()["detail"]
    
    def test_export_signals_csv(self, client):
        """Test CSV export functionality."""
        with patch('services.radar.api.get_market_signals_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.export_signals_csv.return_value = "signal_id,title,priority\nSIG-001,Test Signal,high"
            mock_get_service.return_value = mock_service
            
            response = client.get("/signals/export/csv")
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/csv; charset=utf-8"
            assert "attachment" in response.headers["content-disposition"]
    
    def test_get_stats(self, client):
        """Test getting statistics."""
        with patch('services.radar.api.get_market_signals_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_signal_stats.return_value = {
                "total_signals": 10,
                "type_distribution": {"tender": 5, "notice": 3, "policy_update": 2},
                "priority_distribution": {"high": 4, "medium": 4, "low": 2},
                "recent_activity": {"count": 3, "period": "last_30_days"}
            }
            mock_get_service.return_value = mock_service
            
            response = client.get("/stats")
            assert response.status_code == 200
            
            data = response.json()
            assert data["total_signals"] == 10
            assert "type_distribution" in data
            assert "priority_distribution" in data
            assert "recent_activity" in data
    
    def test_get_enums(self, client):
        """Test getting enum values."""
        response = client.get("/enums")
        assert response.status_code == 200
        
        data = response.json()
        assert "provinces" in data
        assert "asset_types" in data
        assert "signal_types" in data
        assert "priorities" in data
        
        # Check specific enum values
        assert "guangdong" in data["provinces"]
        assert "solar" in data["asset_types"]
        assert "tender" in data["signal_types"]
        assert "high" in data["priorities"]
        
        # Check bilingual labels
        assert data["provinces"]["guangdong"]["label"] == "广东"
        assert data["provinces"]["guangdong"]["label_en"] == "Guangdong"
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        with patch('services.radar.api.get_market_signals_service') as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_signal_stats.return_value = {
                "total_signals": 10,
                "recent_activity": {"count": 3},
                "upcoming_deadlines": {"count": 2}
            }
            mock_get_service.return_value = mock_service
            
            response = client.get("/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "radar"
            assert "stats_summary" in data
            assert data["stats_summary"]["total_signals"] == 10
    
    def test_health_check_failure(self, client):
        """Test health check failure."""
        with patch('services.radar.api.get_market_signals_service', side_effect=Exception("Service error")):
            response = client.get("/health")
            assert response.status_code == 503
            
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "Service error" in data["error"]


class TestMarketSignalsService:
    """Test MarketSignalsService functionality."""
    
    @pytest.fixture
    def service(self):
        """Service fixture."""
        return MarketSignalsService()
    
    @pytest.fixture
    def sample_filter(self):
        """Sample filter fixture."""
        return MarketSignalFilter(
            provinces=[Province.GUANGDONG],
            asset_types=[AssetType.SOLAR],
            signal_types=[SignalType.TENDER],
            priorities=[SignalPriority.HIGH],
            limit=10,
            offset=0
        )
    
    @pytest.mark.asyncio
    async def test_get_signals_no_filter(self, service):
        """Test getting signals without filters."""
        # Wait for initialization
        await service._initialize_sample_data()
        
        filter_obj = MarketSignalFilter(limit=50, offset=0)
        result = await service.get_signals(filter_obj)
        
        assert "signals" in result
        assert "total_count" in result
        assert result["total_count"] > 0
        assert len(result["signals"]) <= 50
    
    @pytest.mark.asyncio
    async def test_get_signals_with_province_filter(self, service):
        """Test getting signals with province filter."""
        await service._initialize_sample_data()
        
        filter_obj = MarketSignalFilter(
            provinces=[Province.GUANGDONG],
            limit=50,
            offset=0
        )
        result = await service.get_signals(filter_obj)
        
        # All returned signals should be from Guangdong
        for signal in result["signals"]:
            assert signal["province"] == "guangdong"
    
    @pytest.mark.asyncio
    async def test_get_signals_with_asset_type_filter(self, service):
        """Test getting signals with asset type filter."""
        await service._initialize_sample_data()
        
        filter_obj = MarketSignalFilter(
            asset_types=[AssetType.SOLAR],
            limit=50,
            offset=0
        )
        result = await service.get_signals(filter_obj)
        
        # All returned signals should be solar-related
        for signal in result["signals"]:
            assert signal["asset_type"] == "solar"
    
    @pytest.mark.asyncio
    async def test_get_signals_with_keywords_filter(self, service):
        """Test getting signals with keywords filter."""
        await service._initialize_sample_data()
        
        filter_obj = MarketSignalFilter(
            keywords="光伏",
            limit=50,
            offset=0
        )
        result = await service.get_signals(filter_obj)
        
        # All returned signals should contain the keyword
        for signal in result["signals"]:
            assert ("光伏" in signal["title"].lower() or 
                   "光伏" in signal["content"].lower() or
                   any("光伏" in tag.lower() for tag in signal["tags"]))
    
    @pytest.mark.asyncio
    async def test_get_signals_with_date_filter(self, service):
        """Test getting signals with date filter."""
        await service._initialize_sample_data()
        
        filter_obj = MarketSignalFilter(
            date_from="2024-01-01",
            date_to="2024-12-31",
            limit=50,
            offset=0
        )
        result = await service.get_signals(filter_obj)
        
        # All returned signals should be within date range
        for signal in result["signals"]:
            assert signal["published_date"] >= "2024-01-01"
            assert signal["published_date"] <= "2024-12-31"
    
    @pytest.mark.asyncio
    async def test_get_signals_with_impact_score_filter(self, service):
        """Test getting signals with minimum impact score filter."""
        await service._initialize_sample_data()
        
        filter_obj = MarketSignalFilter(
            min_impact_score=0.8,
            limit=50,
            offset=0
        )
        result = await service.get_signals(filter_obj)
        
        # All returned signals should have impact score >= 0.8
        for signal in result["signals"]:
            assert signal["impact_score"] >= 0.8
    
    @pytest.mark.asyncio
    async def test_get_signals_pagination(self, service):
        """Test signals pagination."""
        await service._initialize_sample_data()
        
        # First page
        filter_obj = MarketSignalFilter(limit=2, offset=0)
        result1 = await service.get_signals(filter_obj)
        
        # Second page
        filter_obj = MarketSignalFilter(limit=2, offset=2)
        result2 = await service.get_signals(filter_obj)
        
        # Should have different signals
        if len(result1["signals"]) > 0 and len(result2["signals"]) > 0:
            signal_ids_1 = {s["signal_id"] for s in result1["signals"]}
            signal_ids_2 = {s["signal_id"] for s in result2["signals"]}
            assert signal_ids_1.isdisjoint(signal_ids_2)
    
    @pytest.mark.asyncio
    async def test_get_signal_by_id(self, service):
        """Test getting signal by ID."""
        await service._initialize_sample_data()
        
        # Get all signals to find a valid ID
        filter_obj = MarketSignalFilter(limit=1, offset=0)
        result = await service.get_signals(filter_obj)
        
        if result["signals"]:
            signal_id = result["signals"][0]["signal_id"]
            signal = await service.get_signal_by_id(signal_id)
            
            assert signal is not None
            assert signal.signal_id == signal_id
    
    @pytest.mark.asyncio
    async def test_get_signal_by_invalid_id(self, service):
        """Test getting signal by invalid ID."""
        signal = await service.get_signal_by_id("invalid_id")
        assert signal is None
    
    @pytest.mark.asyncio
    async def test_get_signal_stats(self, service):
        """Test getting signal statistics."""
        await service._initialize_sample_data()
        
        stats = await service.get_signal_stats()
        
        assert "total_signals" in stats
        assert "type_distribution" in stats
        assert "priority_distribution" in stats
        assert "province_distribution" in stats
        assert "asset_type_distribution" in stats
        assert "recent_activity" in stats
        assert "upcoming_deadlines" in stats
        
        assert stats["total_signals"] > 0
        assert isinstance(stats["type_distribution"], dict)
        assert isinstance(stats["priority_distribution"], dict)
    
    @pytest.mark.asyncio
    async def test_export_signals_csv(self, service):
        """Test CSV export functionality."""
        await service._initialize_sample_data()
        
        filter_obj = MarketSignalFilter(limit=10, offset=0)
        csv_content = await service.export_signals_csv(filter_obj)
        
        assert isinstance(csv_content, str)
        assert "Signal ID" in csv_content  # Header
        assert "Title" in csv_content
        assert "Priority" in csv_content
        
        # Should have multiple lines (header + data)
        lines = csv_content.strip().split('\n')
        assert len(lines) > 1


class TestMarketSignalFilter:
    """Test MarketSignalFilter validation."""
    
    def test_valid_filter(self):
        """Test creating valid filter."""
        filter_obj = MarketSignalFilter(
            provinces=[Province.GUANGDONG, Province.SHANDONG],
            asset_types=[AssetType.SOLAR, AssetType.WIND],
            signal_types=[SignalType.TENDER],
            priorities=[SignalPriority.HIGH, SignalPriority.MEDIUM],
            date_from="2024-01-01",
            date_to="2024-12-31",
            keywords="光伏",
            min_impact_score=0.5,
            limit=20,
            offset=10
        )
        
        assert len(filter_obj.provinces) == 2
        assert len(filter_obj.asset_types) == 2
        assert filter_obj.keywords == "光伏"
        assert filter_obj.min_impact_score == 0.5
        assert filter_obj.limit == 20
        assert filter_obj.offset == 10
    
    def test_filter_defaults(self):
        """Test filter default values."""
        filter_obj = MarketSignalFilter()
        
        assert filter_obj.provinces is None
        assert filter_obj.asset_types is None
        assert filter_obj.signal_types is None
        assert filter_obj.priorities is None
        assert filter_obj.date_from is None
        assert filter_obj.date_to is None
        assert filter_obj.keywords is None
        assert filter_obj.min_impact_score is None
        assert filter_obj.limit == 50
        assert filter_obj.offset == 0
    
    def test_filter_validation_limits(self):
        """Test filter validation for limits."""
        from pydantic import ValidationError
        
        # Test invalid limit (too high)
        with pytest.raises(ValidationError):
            MarketSignalFilter(limit=300)
        
        # Test invalid limit (too low)
        with pytest.raises(ValidationError):
            MarketSignalFilter(limit=0)
        
        # Test invalid offset
        with pytest.raises(ValidationError):
            MarketSignalFilter(offset=-1)
        
        # Test invalid impact score
        with pytest.raises(ValidationError):
            MarketSignalFilter(min_impact_score=1.5)
        
        with pytest.raises(ValidationError):
            MarketSignalFilter(min_impact_score=-0.1)


class TestRadarUILogic:
    """Test Radar UI logic and interactions."""
    
    def test_priority_color_mapping(self):
        """Test priority color mapping logic."""
        def get_priority_color(priority):
            colors = {
                'critical': '#dc2626',
                'high': '#ea580c',
                'medium': '#d97706',
                'low': '#65a30d'
            }
            return colors.get(priority, '#6b7280')
        
        assert get_priority_color('critical') == '#dc2626'
        assert get_priority_color('high') == '#ea580c'
        assert get_priority_color('medium') == '#d97706'
        assert get_priority_color('low') == '#65a30d'
        assert get_priority_color('unknown') == '#6b7280'
    
    def test_label_localization(self):
        """Test label localization logic."""
        def get_priority_label(priority, lang):
            labels = {
                'critical': {'zh': '紧急', 'en': 'Critical'},
                'high': {'zh': '高', 'en': 'High'},
                'medium': {'zh': '中', 'en': 'Medium'},
                'low': {'zh': '低', 'en': 'Low'}
            }
            return labels.get(priority, {}).get(lang, priority)
        
        assert get_priority_label('high', 'zh') == '高'
        assert get_priority_label('high', 'en') == 'High'
        assert get_priority_label('unknown', 'zh') == 'unknown'
    
    def test_filter_url_params_generation(self):
        """Test URL parameters generation for filters."""
        def build_filter_params(filters):
            params = []
            
            if filters.get('provinces'):
                for p in filters['provinces']:
                    params.append(f'provinces={p}')
            
            if filters.get('keywords'):
                params.append(f'keywords={filters["keywords"]}')
            
            if filters.get('min_impact_score', 0) > 0:
                params.append(f'min_impact_score={filters["min_impact_score"]}')
            
            return '&'.join(params)
        
        filters = {
            'provinces': ['guangdong', 'shandong'],
            'keywords': '光伏',
            'min_impact_score': 0.8
        }
        
        params = build_filter_params(filters)
        assert 'provinces=guangdong' in params
        assert 'provinces=shandong' in params
        assert 'keywords=光伏' in params
        assert 'min_impact_score=0.8' in params
    
    def test_pagination_logic(self):
        """Test pagination calculation logic."""
        def calculate_pagination(total_count, page_size, current_page):
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            offset = (current_page - 1) * page_size
            
            return {
                'total_pages': total_pages,
                'offset': offset,
                'has_previous': current_page > 1,
                'has_next': current_page < total_pages
            }
        
        # Test normal pagination
        result = calculate_pagination(100, 20, 3)
        assert result['total_pages'] == 5
        assert result['offset'] == 40
        assert result['has_previous'] is True
        assert result['has_next'] is True
        
        # Test first page
        result = calculate_pagination(100, 20, 1)
        assert result['has_previous'] is False
        assert result['has_next'] is True
        
        # Test last page
        result = calculate_pagination(100, 20, 5)
        assert result['has_previous'] is True
        assert result['has_next'] is False
        
        # Test empty results
        result = calculate_pagination(0, 20, 1)
        assert result['total_pages'] == 1
        assert result['has_previous'] is False
        assert result['has_next'] is False