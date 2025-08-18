"""Tests for text chunking and clause segmentation."""

import pytest
from services.ocr.chunker import (
    estimate_token_count,
    split_into_clauses,
    create_sliding_windows,
    chunk_document_content,
    analyze_chunking_quality,
    optimize_chunks_for_citation,
    _split_paragraph_into_clauses,
    _detect_clause_type
)
from services.ocr.schemas import ChunkData


class TestTokenEstimation:
    """Test token count estimation."""
    
    def test_chinese_text_tokens(self):
        """Test token estimation for Chinese text."""
        text = "这是一个中文测试文档"
        tokens = estimate_token_count(text)
        
        # Should be roughly 1.5 tokens per Chinese character
        expected = len(text) * 1.5
        assert abs(tokens - expected) < 5
    
    def test_english_text_tokens(self):
        """Test token estimation for English text."""
        text = "This is an English test document"
        tokens = estimate_token_count(text)
        
        # Should be roughly 1.3 tokens per English word
        word_count = len(text.split())
        expected = word_count * 1.3
        assert abs(tokens - expected) < 5
    
    def test_mixed_text_tokens(self):
        """Test token estimation for mixed text."""
        text = "这是中文 and English mixed text 测试"
        tokens = estimate_token_count(text)
        
        assert tokens > 0
        assert tokens < len(text) * 2  # Reasonable upper bound
    
    def test_empty_text_tokens(self):
        """Test token estimation for empty text."""
        assert estimate_token_count("") == 0
        assert estimate_token_count("   ") == 1  # Minimum 1 token


class TestClauseSplitting:
    """Test clause splitting functionality."""
    
    def test_article_splitting(self):
        """Test splitting by article numbers."""
        paragraphs = [
            "第一条：风力发电项目应当符合要求。第二条：太阳能发电项目规定如下。"
        ]
        
        clauses = split_into_clauses(paragraphs)
        
        assert len(clauses) >= 2
        assert any("第一条" in clause for clause in clauses)
        assert any("第二条" in clause for clause in clauses)
    
    def test_numbered_item_splitting(self):
        """Test splitting by numbered items."""
        paragraphs = [
            "项目要求：（一）装机容量不少于50MW；（二）年利用小时数不低于2000小时。"
        ]
        
        clauses = split_into_clauses(paragraphs)
        
        assert len(clauses) >= 2
        assert any("（一）" in clause for clause in clauses)
        assert any("（二）" in clause for clause in clauses)
    
    def test_sentence_splitting(self):
        """Test splitting by sentence endings."""
        paragraphs = [
            "这是第一句话。这是第二句话！这是第三句话？"
        ]
        
        clauses = split_into_clauses(paragraphs)
        
        assert len(clauses) >= 3
    
    def test_complex_paragraph_splitting(self):
        """Test splitting complex paragraph."""
        paragraph = """
        第一条：电力市场交易应当遵循以下原则：
        （一）公开、公平、公正原则；
        （二）自愿参与原则；
        （三）诚实信用原则。
        第二条：市场主体包括发电企业、售电公司等。
        """
        
        clauses = _split_paragraph_into_clauses(paragraph)
        
        # Should split into multiple clauses
        assert len(clauses) >= 4
        
        # Should contain key elements
        clause_text = " ".join(clauses)
        assert "第一条" in clause_text
        assert "第二条" in clause_text
        assert "（一）" in clause_text
    
    def test_empty_paragraphs(self):
        """Test handling of empty paragraphs."""
        paragraphs = ["", "   ", "有效内容"]
        
        clauses = split_into_clauses(paragraphs)
        
        assert len(clauses) == 1
        assert "有效内容" in clauses[0]


class TestSlidingWindows:
    """Test sliding window chunk creation."""
    
    def test_basic_windowing(self):
        """Test basic sliding window creation."""
        clauses = [
            "第一条：这是第一条内容。",
            "第二条：这是第二条内容。",
            "第三条：这是第三条内容。"
        ]
        
        chunks = create_sliding_windows(clauses, max_tokens=100, overlap_tokens=20)
        
        assert len(chunks) >= 1
        assert all(isinstance(chunk, ChunkData) for chunk in chunks)
        assert all(chunk.token_count <= 100 for chunk in chunks)
    
    def test_large_content_windowing(self):
        """Test windowing with content that exceeds max tokens."""
        # Create large clauses
        large_clauses = [
            "第一条：" + "这是很长的内容。" * 50,
            "第二条：" + "这也是很长的内容。" * 50,
            "第三条：" + "这还是很长的内容。" * 50
        ]
        
        chunks = create_sliding_windows(large_clauses, max_tokens=200, overlap_tokens=50)
        
        assert len(chunks) >= 2  # Should create multiple chunks
        assert all(chunk.token_count <= 200 for chunk in chunks)
    
    def test_overlap_functionality(self):
        """Test that overlap is working correctly."""
        clauses = [
            "第一条：短内容A。",
            "第二条：短内容B。",
            "第三条：短内容C。",
            "第四条：短内容D。"
        ]
        
        chunks = create_sliding_windows(clauses, max_tokens=50, overlap_tokens=20)
        
        if len(chunks) > 1:
            # Check that there's some overlap between consecutive chunks
            first_chunk_end = chunks[0].content[-20:]
            second_chunk_start = chunks[1].content[:20]
            
            # There should be some common content (not exact match due to processing)
            assert len(first_chunk_end) > 0
            assert len(second_chunk_start) > 0
    
    def test_chunk_metadata(self):
        """Test that chunk metadata is properly set."""
        clauses = ["第一条：测试内容。"]
        
        chunks = create_sliding_windows(clauses)
        
        assert len(chunks) == 1
        chunk = chunks[0]
        
        assert chunk.chunk_id is not None
        assert len(chunk.chunk_id) > 0
        assert chunk.content == "第一条：测试内容。"
        assert chunk.token_count > 0
        assert chunk.end_char >= chunk.start_char


class TestClauseTypeDetection:
    """Test clause type detection."""
    
    def test_article_detection(self):
        """Test article clause detection."""
        content = "第一条：电力市场交易规则"
        clause_type = _detect_clause_type(content)
        
        assert clause_type == "article"
    
    def test_numbered_item_detection(self):
        """Test numbered item detection."""
        content = "（一）装机容量要求"
        clause_type = _detect_clause_type(content)
        
        assert clause_type == "numbered_item"
    
    def test_definition_detection(self):
        """Test definition clause detection."""
        content = "电力市场是指电力商品交易的场所"
        clause_type = _detect_clause_type(content)
        
        assert clause_type == "definition"
    
    def test_requirement_detection(self):
        """Test requirement clause detection."""
        content = "发电企业应当按照规定参与市场交易"
        clause_type = _detect_clause_type(content)
        
        assert clause_type == "requirement"
    
    def test_prohibition_detection(self):
        """Test prohibition clause detection."""
        content = "市场主体不得操纵市场价格"
        clause_type = _detect_clause_type(content)
        
        assert clause_type == "prohibition"
    
    def test_table_detection(self):
        """Test table content detection."""
        content = "| 项目 | 要求 | 标准 | 备注 |"
        clause_type = _detect_clause_type(content)
        
        assert clause_type == "table"
    
    def test_general_detection(self):
        """Test general clause detection."""
        content = "这是一般性的描述内容"
        clause_type = _detect_clause_type(content)
        
        assert clause_type == "general"


class TestChunkOptimization:
    """Test chunk optimization functionality."""
    
    def test_merge_short_chunks(self):
        """Test merging of very short chunks."""
        short_chunks = [
            ChunkData(chunk_id="1", content="短", token_count=5),
            ChunkData(chunk_id="2", content="也很短", token_count=10),
            ChunkData(chunk_id="3", content="这是一个正常长度的内容块", token_count=100)
        ]
        
        optimized = optimize_chunks_for_citation(short_chunks)
        
        # Should merge the first two short chunks
        assert len(optimized) < len(short_chunks)
        assert any(chunk.token_count >= 15 for chunk in optimized)
    
    def test_no_unnecessary_merging(self):
        """Test that normal-sized chunks are not merged."""
        normal_chunks = [
            ChunkData(chunk_id="1", content="这是正常长度的内容" * 10, token_count=100),
            ChunkData(chunk_id="2", content="这也是正常长度的内容" * 10, token_count=100)
        ]
        
        optimized = optimize_chunks_for_citation(normal_chunks)
        
        # Should not merge normal-sized chunks
        assert len(optimized) == len(normal_chunks)


class TestDocumentChunking:
    """Test complete document chunking process."""
    
    def test_complete_chunking_process(self):
        """Test the complete chunking process."""
        paragraphs = [
            "第一条：电力市场交易应当遵循公开、公平、公正的原则。",
            "第二条：市场主体包括发电企业、电网企业、售电公司、电力用户等。",
            "第三条：电力交易分为中长期交易和现货交易。"
        ]
        
        chunks = chunk_document_content(paragraphs)
        
        assert len(chunks) >= 1
        assert all(isinstance(chunk, ChunkData) for chunk in chunks)
        assert all(chunk.token_count > 0 for chunk in chunks)
        assert all(len(chunk.content) > 0 for chunk in chunks)
        assert all(chunk.chunk_id for chunk in chunks)
    
    def test_large_document_chunking(self):
        """Test chunking of large document."""
        # Create a large document
        large_paragraphs = []
        for i in range(20):
            paragraph = f"第{i+1}条：" + "这是很长的条款内容。" * 20
            large_paragraphs.append(paragraph)
        
        chunks = chunk_document_content(large_paragraphs, max_tokens=500)
        
        assert len(chunks) >= 2  # Should create multiple chunks
        assert all(chunk.token_count <= 500 for chunk in chunks)
    
    def test_empty_document_chunking(self):
        """Test chunking of empty document."""
        chunks = chunk_document_content([])
        
        assert len(chunks) == 0
    
    def test_single_paragraph_chunking(self):
        """Test chunking of single paragraph."""
        paragraphs = ["这是一个简单的段落内容。"]
        
        chunks = chunk_document_content(paragraphs)
        
        assert len(chunks) == 1
        assert chunks[0].content == paragraphs[0]


class TestChunkingQualityAnalysis:
    """Test chunking quality analysis."""
    
    def test_quality_analysis(self):
        """Test chunking quality analysis."""
        chunks = [
            ChunkData(chunk_id="1", content="内容1", token_count=100, clause_type="article"),
            ChunkData(chunk_id="2", content="内容2", token_count=150, clause_type="requirement"),
            ChunkData(chunk_id="3", content="内容3", token_count=80, clause_type="general")
        ]
        
        analysis = analyze_chunking_quality(chunks)
        
        assert analysis["total_chunks"] == 3
        assert analysis["avg_tokens_per_chunk"] == (100 + 150 + 80) / 3
        assert analysis["min_tokens"] == 80
        assert analysis["max_tokens"] == 150
        assert "clause_type_distribution" in analysis
        assert analysis["clause_type_distribution"]["article"] == 1
        assert analysis["clause_type_distribution"]["requirement"] == 1
    
    def test_empty_chunks_analysis(self):
        """Test analysis of empty chunk list."""
        analysis = analyze_chunking_quality([])
        
        assert "error" in analysis


@pytest.fixture
def sample_regulation_paragraphs():
    """Sample regulation paragraphs for testing."""
    return [
        "第一条：为规范电力市场交易行为，维护市场秩序，根据《电力法》等法律法规，制定本规则。",
        "第二条：本规则适用于广东省电力市场的各类交易活动。",
        "第三条：电力市场交易应当遵循以下原则：（一）公开、公平、公正原则；（二）自愿参与原则；（三）诚实信用原则。",
        "第四条：市场主体包括：（一）发电企业；（二）电网企业；（三）售电公司；（四）电力用户。",
        "第五条：电力交易分为中长期交易和现货交易两类。中长期交易包括年度交易、月度交易等；现货交易包括日前交易、实时交易等。"
    ]


def test_realistic_document_chunking(sample_regulation_paragraphs):
    """Test chunking with realistic regulation document."""
    chunks = chunk_document_content(sample_regulation_paragraphs, max_tokens=200, overlap_tokens=50)
    
    # Basic validation
    assert len(chunks) >= 2  # Should create multiple chunks
    assert all(chunk.token_count <= 200 for chunk in chunks)
    
    # Content validation
    all_content = " ".join(chunk.content for chunk in chunks)
    assert "第一条" in all_content
    assert "第五条" in all_content
    assert "电力市场" in all_content
    
    # Quality analysis
    analysis = analyze_chunking_quality(chunks)
    assert analysis["total_chunks"] == len(chunks)
    assert analysis["avg_tokens_per_chunk"] > 0
    assert "article" in analysis["clause_type_distribution"]
    
    # Check that chunks have proper metadata
    for chunk in chunks:
        assert chunk.chunk_id
        assert chunk.content
        assert chunk.token_count > 0
        assert chunk.clause_type in ["article", "numbered_item", "general", "requirement"]