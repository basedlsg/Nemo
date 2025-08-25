"""Answer composer service for Task 13 - quote-first Chinese responses with citations."""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CitationReference:
    """Citation reference for inline citations."""
    citation_id: str
    title: str
    effective_date: str
    url: str
    passage: str
    score: float


@dataclass
class AnswerSection:
    """Section of the composed answer."""
    title: str
    bullets: List[str]
    citations: List[CitationReference]


class ChineseAnswerComposer:
    """
    Answer composer that creates quote-first Chinese responses with inline citations.
    
    Template format:
    **并网验收要点（广东 / 光伏）**
    - 资料清单：
      • <clause from citation A> 〔《{titleA}》，生效：{dateA}〕
      • <clause from citation B> 〔《{titleB}》，生效：{dateB}〕
    - 受理与时限：
      • <clause> 〔《...》，生效：...〕
    """
    
    def __init__(self):
        """Initialize answer composer."""
        self.province_labels = {
            "guangdong": "广东",
            "shandong": "山东", 
            "inner_mongolia": "内蒙古"
        }
        
        self.asset_labels = {
            "wind": "风电",
            "solar": "光伏",
            "bess": "储能",
            "coal_flex": "煤电"
        }
        
        self.doc_class_labels = {
            "market_rules": "市场规则",
            "grid_connection": "并网",
            "dispatch_ops": "调度"
        }
    
    def compose_answer(
        self,
        search_results: List[Dict[str, Any]],
        query: Dict[str, Any],
        max_citations: int = 10
    ) -> Dict[str, Any]:
        """Compose answer using Gemini if enabled, otherwise use template-based approach."""
        # Check if Gemini composer is enabled
        import os
        use_gemini = os.getenv("FEATURE_GEMINI_COMPOSER", "false").lower() == "true"

        if use_gemini:
            try:
                from services.gemini.composer import GeminiAnswerComposer
                gemini_composer = GeminiAnswerComposer()
                return gemini_composer.compose_answer(search_results, query, max_citations)
            except Exception as e:
                logger.warning(f"Gemini composer failed, falling back to template: {e}")
                # Fall through to template-based approach

        # Original template-based approach
        try:
            if not search_results:
                return self._create_refusal_response("没有找到相关的一手资料")
            
            # Extract and validate citations
            citations = self._extract_citations(search_results, max_citations)
            
            if not citations:
                return self._create_refusal_response("没有找到有效的引用资料")
            
            # Group citations by topic/requirement
            sections = self._group_citations_by_topic(citations, query)
            
            # Generate answer title
            answer_title = self._generate_answer_title(query)
            
            # Compose answer sections
            answer_text = self._compose_answer_text(answer_title, sections)
            
            # Add English summary if requested
            if query.get("lang") == "en":
                english_summary = self._generate_english_summary(sections)
                answer_text += f"\n\n**English Summary:**\n{english_summary}"
            
            # Prepare citation metadata
            citation_metadata = [
                {
                    "citation_id": citation.citation_id,
                    "title": citation.title,
                    "url": citation.url,
                    "effective_date": citation.effective_date,
                    "score": citation.score
                }
                for citation in citations
            ]
            
            return {
                "answer_zh": answer_text,
                "citations": citation_metadata,
                "sections": len(sections),
                "total_citations": len(citations),
                "composed_at": datetime.utcnow().isoformat(),
                "query_context": {
                    "province": query.get("province"),
                    "asset": query.get("asset"),
                    "doc_class": query.get("doc_class")
                }
            }
            
        except Exception as e:
            logger.error(f"Answer composition failed: {e}")
            return self._create_refusal_response("答案生成过程中出现错误")
    
    def _extract_citations(
        self, 
        search_results: List[Dict[str, Any]], 
        max_citations: int
    ) -> List[CitationReference]:
        """Extract and validate citations from search results."""
        citations = []
        
        for result in search_results[:max_citations]:
            try:
                metadata = result.get("metadata", {})
                
                # Validate required fields
                if not all([
                    result.get("citation_id"),
                    metadata.get("title"),
                    metadata.get("effective_date"),
                    result.get("passage")
                ]):
                    logger.warning(f"Skipping citation with missing fields: {result.get('citation_id')}")
                    continue
                
                citation = CitationReference(
                    citation_id=result["citation_id"],
                    title=metadata["title"],
                    effective_date=metadata["effective_date"],
                    url=metadata.get("url", ""),
                    passage=result["passage"],
                    score=result.get("score", 0.0)
                )
                
                citations.append(citation)
                
            except Exception as e:
                logger.error(f"Failed to extract citation: {e}")
        
        return citations
    
    def _group_citations_by_topic(
        self, 
        citations: List[CitationReference], 
        query: Dict[str, Any]
    ) -> List[AnswerSection]:
        """Group citations by topic/requirement."""
        # Simplified grouping - in production, this could use more sophisticated topic modeling
        
        # Common energy regulation topics
        topic_keywords = {
            "资料清单": ["资料", "文件", "材料", "证明", "申请", "备案"],
            "受理与时限": ["受理", "时限", "期限", "工作日", "审批", "办理"],
            "技术要求": ["技术", "标准", "规范", "参数", "指标", "要求"],
            "安全规定": ["安全", "保护", "防护", "监控", "检测", "维护"],
            "并网条件": ["并网", "接入", "连接", "容量", "电压", "频率"],
            "市场准入": ["准入", "资格", "条件", "门槛", "认证", "许可"]
        }
        
        sections = []
        used_citations = set()
        
        # Group citations by topic
        for topic, keywords in topic_keywords.items():
            topic_citations = []
            
            for citation in citations:
                if citation.citation_id in used_citations:
                    continue
                
                # Check if citation content matches topic keywords
                content = citation.passage.lower()
                if any(keyword in content for keyword in keywords):
                    topic_citations.append(citation)
                    used_citations.add(citation.citation_id)
            
            if topic_citations:
                # Create bullets from citation passages
                bullets = []
                for citation in topic_citations:
                    # Extract key clause from passage
                    clause = self._extract_key_clause(citation.passage)
                    bullet = f"• {clause} 〔《{citation.title}》，生效：{citation.effective_date}〕"
                    bullets.append(bullet)
                
                section = AnswerSection(
                    title=topic,
                    bullets=bullets,
                    citations=topic_citations
                )
                sections.append(section)
        
        # Add remaining citations to a general section
        remaining_citations = [c for c in citations if c.citation_id not in used_citations]
        if remaining_citations:
            bullets = []
            for citation in remaining_citations:
                clause = self._extract_key_clause(citation.passage)
                bullet = f"• {clause} 〔《{citation.title}》，生效：{citation.effective_date}〕"
                bullets.append(bullet)
            
            section = AnswerSection(
                title="相关规定",
                bullets=bullets,
                citations=remaining_citations
            )
            sections.append(section)
        
        return sections
    
    def _extract_key_clause(self, passage: str) -> str:
        """Extract key clause from passage for citation."""
        if not passage:
            return "相关规定"
        
        # Clean up passage
        cleaned = passage.strip()
        
        # If passage is short, use as-is
        if len(cleaned) <= 100:
            return cleaned
        
        # Try to find complete sentences
        sentences = re.split(r'[。！？]', cleaned)
        if sentences and len(sentences[0]) <= 150:
            return sentences[0] + "。"
        
        # Truncate to reasonable length
        if len(cleaned) > 150:
            return cleaned[:147] + "..."
        
        return cleaned
    
    def _generate_answer_title(self, query: Dict[str, Any]) -> str:
        """Generate answer title based on query context."""
        province = query.get("province", "")
        asset = query.get("asset", "")
        doc_class = query.get("doc_class", "")
        
        province_label = self.province_labels.get(province, province)
        asset_label = self.asset_labels.get(asset, asset) if asset else ""
        doc_class_label = self.doc_class_labels.get(doc_class, doc_class)
        
        if asset_label:
            return f"**{doc_class_label}要点（{province_label} / {asset_label}）**"
        else:
            return f"**{doc_class_label}要点（{province_label}）**"
    
    def _compose_answer_text(self, title: str, sections: List[AnswerSection]) -> str:
        """Compose final answer text with sections and citations."""
        answer_parts = [title]
        
        for section in sections:
            answer_parts.append(f"- {section.title}：")
            answer_parts.extend([f"  {bullet}" for bullet in section.bullets])
        
        # Add refusal note if no valid clauses
        if not any(section.bullets for section in sections):
            answer_parts.append("\n（若找不到一手来源：直接拒答并说明）")
        
        return "\n".join(answer_parts)
    
    def _generate_english_summary(self, sections: List[AnswerSection]) -> str:
        """Generate optional English summary."""
        # Simplified English summary - in production, this could use translation services
        summary_parts = []
        
        for section in sections:
            section_summary = f"**{section.title}**: {len(section.bullets)} requirements found"
            summary_parts.append(section_summary)
        
        summary = "This response covers " + ", ".join(summary_parts) + "."
        summary += f" Total citations: {sum(len(section.citations) for section in sections)}."
        
        return summary
    
    def _create_refusal_response(self, reason: str) -> Dict[str, Any]:
        """Create refusal response when no valid answer can be composed."""
        return {
            "answer_zh": f"抱歉，{reason}。请尝试更具体的问题或联系相关部门获取最新信息。",
            "citations": [],
            "sections": 0,
            "total_citations": 0,
            "refusal_reason": reason,
            "composed_at": datetime.utcnow().isoformat()
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Check answer composer health."""
        try:
            # Test basic functionality
            test_results = [{
                "citation_id": "test",
                "passage": "测试内容",
                "score": 0.8,
                "metadata": {
                    "title": "测试文档",
                    "effective_date": "2025-01-01",
                    "url": "https://example.com"
                }
            }]
            
            test_query = {
                "province": "guangdong",
                "asset": "solar",
                "doc_class": "grid_connection"
            }
            
            result = self.compose_answer(test_results, test_query)
            
            return {
                "status": "healthy",
                "test_composition": "success" if result.get("answer_zh") else "failed",
                "province_labels": len(self.province_labels),
                "asset_labels": len(self.asset_labels),
                "doc_class_labels": len(self.doc_class_labels),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Composer health check failed: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global composer instance
_answer_composer: Optional[ChineseAnswerComposer] = None


def get_answer_composer() -> ChineseAnswerComposer:
    """Get global answer composer instance."""
    global _answer_composer
    if _answer_composer is None:
        _answer_composer = ChineseAnswerComposer()
    return _answer_composer


def compose_answer(
    search_results: List[Dict[str, Any]], 
    query: Dict[str, Any]
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Convenience function for answer composition.
    
    Args:
        search_results: Results from retriever service
        query: Original query parameters
        
    Returns:
        Tuple of (answer_text, citations_list)
    """
    composer = get_answer_composer()
    result = composer.compose_answer(search_results, query)
    
    return result.get("answer_zh", ""), result.get("citations", [])


if __name__ == "__main__":
    # Quick test of answer composer
    import json
    
    def test_composer():
        print("=== Answer Composer Test ===")
        
        composer = ChineseAnswerComposer()
        
        # Test health check
        print("\n--- Health Check ---")
        health = composer.health_check()
        print(f"Status: {health['status']}")
        
        # Test answer composition
        print("\n--- Answer Composition Test ---")
        test_results = [
            {
                "citation_id": "cite-1",
                "passage": "光伏发电项目并网需要提交项目备案文件、设备技术参数和安全评估报告。",
                "score": 0.9,
                "metadata": {
                    "title": "广东省光伏并网管理办法",
                    "effective_date": "2025-01-01",
                    "url": "https://gzpec.cn/solar-rules"
                }
            },
            {
                "citation_id": "cite-2", 
                "passage": "并网申请受理时限为15个工作日，审批时限为30个工作日。",
                "score": 0.8,
                "metadata": {
                    "title": "分布式光伏接入管理规定",
                    "effective_date": "2024-12-01",
                    "url": "https://gzpec.cn/solar-access"
                }
            }
        ]
        
        test_query = {
            "province": "guangdong",
            "asset": "solar", 
            "doc_class": "grid_connection",
            "question": "光伏并网需要什么资料？"
        }
        
        result = composer.compose_answer(test_results, test_query)
        
        print(f"Answer composed: {len(result.get('answer_zh', ''))} characters")
        print(f"Citations: {result.get('total_citations', 0)}")
        print(f"Sections: {result.get('sections', 0)}")
        
        print("\n--- Answer Text ---")
        print(result.get("answer_zh", ""))
        
        print("\n--- Citations ---")
        for citation in result.get("citations", []):
            print(f"- {citation['title']} ({citation['effective_date']})")
    
    test_composer()
