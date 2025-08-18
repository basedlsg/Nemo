"""Tests for OCR worker integration."""

import pytest
from datetime import date
from uuid import uuid4

from services.ocr.worker import OcrWorker, create_ocr_job_from_message
from services.ocr.schemas import OcrJob, OcrStatus
from services.ocr.docai_client import DocAIClientMock
from services.ocr.storage import GCSStorageClientMock


class TestOcrWorker:
    """Test OCR worker functionality."""
    
    @pytest.fixture
    def mock_worker(self):
        """Create OCR worker with mock dependencies."""
        return OcrWorker(use_mock=True)
    
    @pytest.fixture
    def sample_job(self):
        """Create sample OCR job."""
        return OcrJob(
            gcs_uri="gs://test-bucket/test-doc.pdf",
            province="guangdong",
            doc_class="grid_connection",
            source_url="https://example.com/test-doc",
            checksum="a" * 64,  # Valid SHA256
            title="测试文档",
            source_domain="example.com",
            trace_id="test-trace-123"
        )
    
    def test_successful_job_processing(self, mock_worker, sample_job):
        """Test successful job processing."""
        result = mock_worker.process_job(sample_job)
        
        assert result.job_id == sample_job.job_id
        assert result.status == OcrStatus.SUCCESS
        assert result.citation_id is not None
        assert result.processing_time_ms > 0
        assert result.pages_processed > 0
        assert result.is_success()
    
    def test_job_with_effective_date(self, mock_worker):
        """Test job processing with effective date extraction."""
        job = OcrJob(
            gcs_uri="gs://test-bucket/regulation.pdf",
            province="guangdong",
            doc_class="market_rules",
            source_url="https://example.com/regulation",
            checksum="b" * 64,
            title="电力市场交易规则"
        )
        
        # Mock client should return content with date
        mock_worker.docai_client.mock_responses["gs://test-bucket/regulation.pdf"] = {
            "text": "本规则自2025年3月1日起施行。第一条：电力市场交易规则。",
            "pages": [{"page_number": 1, "blocks": [], "tables": []}],
            "_processing_metadata": {"processing_time_ms": 100}
        }
        
        result = mock_worker.process_job(job)
        
        assert result.is_success()
        assert result.effective_date_found is True
        assert result.normalized_content.effective_date == date(2025, 3, 1)
    
    def test_job_with_tables(self, mock_worker):
        """Test job processing with table extraction."""
        job = OcrJob(
            gcs_uri="gs://test-bucket/table-doc.pdf",
            province="shandong",
            doc_class="dispatch_ops",
            source_url="https://example.com/table-doc",
            checksum="c" * 64,
            title="调度运行规程"
        )
        
        result = mock_worker.process_job(job)
        
        assert result.is_success()
        assert result.tables_extracted >= 0  # Mock may or may not have tables
    
    def test_batch_processing(self, mock_worker):
        """Test batch job processing."""
        jobs = []
        for i in range(3):
            job = OcrJob(
                gcs_uri=f"gs://test-bucket/doc-{i}.pdf",
                province="guangdong",
                doc_class="grid_connection",
                source_url=f"https://example.com/doc-{i}",
                checksum=f"{i}" * 64,
                title=f"文档{i}"
            )
            jobs.append(job)
        
        results = mock_worker.process_batch(jobs)
        
        assert len(results) == 3
        assert all(result.is_success() for result in results)
        assert all(result.citation_id is not None for result in results)
    
    def test_error_handling(self, mock_worker):
        """Test error handling in job processing."""
        # Create job with invalid GCS URI to trigger error
        invalid_job = OcrJob(
            gcs_uri="invalid-uri",
            province="guangdong",
            doc_class="grid_connection",
            source_url="https://example.com/invalid",
            checksum="d" * 64,
            title="Invalid Document"
        )
        
        result = mock_worker.process_job(invalid_job)
        
        assert result.status == OcrStatus.FAILED
        assert result.error_message is not None
        assert not result.is_success()
    
    def test_health_check(self, mock_worker):
        """Test worker health check."""
        health = mock_worker.health_check()
        
        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert "dependencies" in health
        assert "document_ai" in health["dependencies"]
        assert "storage" in health["dependencies"]
    
    def test_metrics_collection(self, mock_worker, sample_job):
        """Test metrics collection."""
        # Process a job to generate metrics
        result = mock_worker.process_job(sample_job)
        
        metrics = mock_worker.get_metrics()
        
        assert "total_jobs" in metrics
        assert metrics["total_jobs"] >= 1
        assert "successful_jobs" in metrics
        assert "avg_processing_time_ms" in metrics


class TestJobCreation:
    """Test OCR job creation utilities."""
    
    def test_create_job_from_message(self):
        """Test creating job from Pub/Sub message."""
        message_data = {
            "gcs_uri": "gs://bucket/doc.pdf",
            "province": "guangdong",
            "doc_class": "market_rules",
            "source_url": "https://example.com/doc",
            "checksum": "e" * 64,
            "title": "市场规则",
            "source_domain": "example.com",
            "trace_id": "trace-456"
        }
        
        job = create_ocr_job_from_message(message_data)
        
        assert job.gcs_uri == message_data["gcs_uri"]
        assert job.province == message_data["province"]
        assert job.doc_class == message_data["doc_class"]
        assert job.source_url == message_data["source_url"]
        assert job.checksum == message_data["checksum"]
        assert job.title == message_data["title"]
        assert job.trace_id == message_data["trace_id"]
    
    def test_create_job_minimal_data(self):
        """Test creating job with minimal required data."""
        message_data = {
            "gcs_uri": "gs://bucket/doc.pdf",
            "province": "guangdong",
            "doc_class": "grid_connection",
            "source_url": "https://example.com/doc",
            "checksum": "f" * 64
        }
        
        job = create_ocr_job_from_message(message_data)
        
        assert job.gcs_uri == message_data["gcs_uri"]
        assert job.title is None
        assert job.trace_id is None


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""
    
    @pytest.fixture
    def worker_with_mocks(self):
        """Create worker with detailed mock setup."""
        docai_client = DocAIClientMock()
        storage_client = GCSStorageClientMock()
        
        # Set up realistic mock responses
        docai_client.mock_responses["gs://test-bucket/guangdong-grid.pdf"] = {
            "text": """
            广东省电网接入管理办法
            
            第一条：为规范电网接入管理，根据《电力法》制定本办法。
            本办法自2025年4月1日起施行。
            
            第二条：电网接入应当符合以下技术要求：
            （一）电压等级符合规定；
            （二）保护装置完善；
            （三）通信设备齐全。
            
            第三条：接入流程包括申请、审查、验收等环节。
            """,
            "pages": [
                {
                    "page_number": 1,
                    "blocks": [
                        {
                            "layout": {
                                "text_anchor": {
                                    "text_segments": [{"start_index": 0, "end_index": 100}]
                                },
                                "confidence": 0.95
                            }
                        }
                    ],
                    "tables": [
                        {
                            "header_rows": [
                                {
                                    "cells": [
                                        {"layout": {"text_anchor": {"text_segments": [{"start_index": 200, "end_index": 204}]}}},
                                        {"layout": {"text_anchor": {"text_segments": [{"start_index": 205, "end_index": 209}]}}}
                                    ]
                                }
                            ],
                            "body_rows": [
                                {
                                    "cells": [
                                        {"layout": {"text_anchor": {"text_segments": [{"start_index": 210, "end_index": 214}]}}},
                                        {"layout": {"text_anchor": {"text_segments": [{"start_index": 215, "end_index": 219}]}}}
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ],
            "entities": [
                {
                    "type": "DATE",
                    "mention_text": "2025年4月1日",
                    "confidence": 0.9
                }
            ],
            "_processing_metadata": {
                "processing_time_ms": 1500,
                "processor_name": "mock-processor"
            }
        }
        
        return OcrWorker(
            docai_client=docai_client,
            storage_client=storage_client,
            citation_crud=None,  # No database for this test
            use_mock=False
        )
    
    def test_realistic_guangdong_grid_document(self, worker_with_mocks):
        """Test processing realistic Guangdong grid connection document."""
        job = OcrJob(
            gcs_uri="gs://test-bucket/guangdong-grid.pdf",
            province="guangdong",
            doc_class="grid_connection",
            source_url="https://gzpec.cn/grid-connection-rules",
            checksum="1234567890abcdef" * 4,
            title="广东省电网接入管理办法",
            source_domain="gzpec.cn"
        )
        
        result = worker_with_mocks.process_job(job)
        
        # Verify successful processing
        assert result.is_success()
        assert result.citation_id is not None
        assert result.processing_time_ms > 0
        
        # Verify content extraction
        assert result.normalized_content is not None
        assert len(result.normalized_content.paragraphs) >= 3
        assert result.normalized_content.language == "zh-CN"
        assert result.normalized_content.page_count == 1
        
        # Verify effective date extraction
        assert result.effective_date_found is True
        assert result.normalized_content.effective_date == date(2025, 4, 1)
        
        # Verify table extraction
        assert result.tables_extracted >= 1
        assert len(result.normalized_content.tables) >= 1
        
        # Verify chunking
        assert len(result.chunks) >= 1
        assert all(chunk.content for chunk in result.chunks)
        assert all(chunk.chunk_id for chunk in result.chunks)
        
        # Verify content quality
        combined_content = " ".join(chunk.content for chunk in result.chunks)
        assert "电网接入" in combined_content
        assert "第一条" in combined_content
        assert "技术要求" in combined_content
    
    def test_document_without_effective_date(self, worker_with_mocks):
        """Test processing document without clear effective date."""
        # Add mock response without effective date
        worker_with_mocks.docai_client.mock_responses["gs://test-bucket/no-date.pdf"] = {
            "text": "这是一个没有明确生效日期的技术规范文档。包含各种技术要求和标准。",
            "pages": [{"page_number": 1, "blocks": [], "tables": []}],
            "_processing_metadata": {"processing_time_ms": 800}
        }
        
        job = OcrJob(
            gcs_uri="gs://test-bucket/no-date.pdf",
            province="shandong",
            doc_class="dispatch_ops",
            source_url="https://example.com/no-date",
            checksum="abcdef1234567890" * 4,
            title="技术规范"
        )
        
        result = worker_with_mocks.process_job(job)
        
        assert result.is_success()
        assert result.effective_date_found is False
        assert result.normalized_content.effective_date is None
    
    def test_storage_artifact_creation(self, worker_with_mocks):
        """Test that storage artifacts are created correctly."""
        job = OcrJob(
            gcs_uri="gs://test-bucket/guangdong-grid.pdf",
            province="guangdong",
            doc_class="grid_connection",
            source_url="https://example.com/test",
            checksum="fedcba0987654321" * 4,
            title="测试文档"
        )
        
        result = worker_with_mocks.process_job(job)
        
        assert result.is_success()
        
        # Check that storage paths are set
        assert result.parsed_gcs_path is not None
        assert result.normalized_gcs_path is not None
        
        # Verify artifacts were stored (in mock storage)
        storage_client = worker_with_mocks.storage_client
        assert storage_client.blob_exists(result.parsed_gcs_path)
        assert storage_client.blob_exists(result.normalized_gcs_path)
        
        # Verify content of stored artifacts
        parsed_content = storage_client.read_gcs_json(result.parsed_gcs_path)
        assert parsed_content is not None
        assert "text" in parsed_content
        
        normalized_content = storage_client.read_gcs_bytes(result.normalized_gcs_path)
        assert normalized_content is not None


@pytest.fixture
def sample_chinese_regulation():
    """Sample Chinese regulation text for testing."""
    return """
    山东省发展和改革委员会
    
    关于印发《山东省电力调度运行规程》的通知
    
    鲁发改能源〔2025〕12号
    
    各市发展改革委，国网山东省电力公司：
    
    为规范电力调度运行管理，保障电力系统安全稳定运行，根据国家有关规定，
    我委制定了《山东省电力调度运行规程》，现印发给你们，请认真贯彻执行。
    本规程自2025年5月1日起施行。
    
    第一条：电力调度应当遵循统一调度、分级管理的原则。
    
    第二条：调度机构职责包括：
    （一）制定调度计划；
    （二）监控系统运行；
    （三）处理异常情况。
    
    第三条：发电企业应当服从调度指令，确保电力供应。
    
    山东省发展和改革委员会
    2025年4月15日
    """


def test_end_to_end_processing(sample_chinese_regulation):
    """Test end-to-end processing with realistic Chinese regulation."""
    # Create worker with mocks
    worker = OcrWorker(use_mock=True)
    
    # Set up mock response with the regulation text
    worker.docai_client.mock_responses["gs://test-bucket/shandong-dispatch.pdf"] = {
        "text": sample_chinese_regulation,
        "pages": [{"page_number": 1, "blocks": [], "tables": []}],
        "_processing_metadata": {"processing_time_ms": 2000}
    }
    
    # Create job
    job = OcrJob(
        gcs_uri="gs://test-bucket/shandong-dispatch.pdf",
        province="shandong",
        doc_class="dispatch_ops",
        source_url="https://shandong.gov.cn/dispatch-rules",
        checksum="1111222233334444" * 4,
        title="山东省电力调度运行规程",
        source_domain="shandong.gov.cn"
    )
    
    # Process job
    result = worker.process_job(job)
    
    # Comprehensive validation
    assert result.is_success()
    assert result.citation_id is not None
    assert result.processing_time_ms > 0
    
    # Content validation
    assert result.normalized_content.language == "zh-CN"
    assert result.effective_date_found is True
    assert result.normalized_content.effective_date == date(2025, 5, 1)
    
    # Chunking validation
    assert len(result.chunks) >= 3  # Should have multiple chunks
    
    # Content quality validation
    all_content = " ".join(chunk.content for chunk in result.chunks)
    assert "电力调度" in all_content
    assert "第一条" in all_content
    assert "第二条" in all_content
    assert "第三条" in all_content
    assert "调度机构" in all_content
    assert "发电企业" in all_content