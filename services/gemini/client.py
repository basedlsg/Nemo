"""Gemini API client for enhanced text parsing and answer generation."""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import time

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from .schemas import GeminiConfig, GeminiRequest, GeminiResponse

logger = logging.getLogger(__name__)


class GeminiClient:
    """Gemini API client for generating answers from structured documents."""

    def __init__(self, config: Optional[GeminiConfig] = None):
        """Initialize Gemini client with configuration."""
        self.config = config or GeminiConfig()

        # Configure Gemini API
        genai.configure(api_key=self.config.api_key)

        # Initialize model
        self.model = genai.GenerativeModel(
            model_name=self.config.model,
            generation_config=GenerationConfig(
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_tokens,
                top_p=0.8,
                top_k=40,
            )
        )

        logger.info(f"Initialized Gemini client with model: {self.config.model}")

    async def generate_answer(self, request: GeminiRequest) -> GeminiResponse:
        """Generate answer from structured document content using Gemini."""
        start_time = time.time()

        try:
            # Build prompt for Gemini
            prompt = self._build_prompt(request)

            # Generate response
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.model.generate_content,
                prompt
            )

            # Parse Gemini response
            answer_data = self._parse_gemini_response(response.text, request)

            # Create response object
            processing_time_ms = int((time.time() - start_time) * 1000)

            return GeminiResponse(
                answer_zh=answer_data.get("answer_zh", ""),
                citations=answer_data.get("citations", []),
                sections=answer_data.get("sections", []),
                confidence_score=answer_data.get("confidence_score", 0.0),
                grounding_score=answer_data.get("grounding_score", 0.0),
                processing_time_ms=processing_time_ms
            )

        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            raise

    def _build_prompt(self, request: GeminiRequest) -> str:
        """Build structured prompt for Gemini."""
        context = request.query_context

        prompt = f"""
你是一个专业的中国能源法规咨询助手。请根据提供的法规文档内容，回答用户的问题。

**用户信息:**
- 省份: {context.get('province', '未知')}
- 资产类型: {context.get('asset', '未知')}
- 文档类型: {context.get('doc_class', '未知')}
- 语言: {context.get('lang', 'zh-CN')}

**用户问题:**
{request.question}

**法规文档结构:**

"""

        # Add document structure
        doc_structure = request.document_structure
        prompt += f"**文档标题:** {doc_structure.title}\n"
        prompt += f"**来源:** {doc_structure.url}\n\n"

        if doc_structure.sections:
            for i, section in enumerate(doc_structure.sections[:10]):  # Limit to top 10 sections
                prompt += f"**第{i+1}部分 ({section.section_type}):**\n"
                prompt += f"标题: {section.title}\n"
                prompt += f"内容: {section.content[:1000]}...\n\n"  # Limit content length

        prompt += """
**回答要求:**
1. 直接引用法规原文，不要编造内容
2. 每个要点必须标注引用的法规来源
3. 使用中文回答，结构清晰
4. 回答要准确、具体、有操作性
5. 如果无法从提供的法规中找到答案，请明确说明

**输出格式:**
请以结构化的方式回答，包括以下部分：
- 核心要点
- 具体要求
- 实施步骤（如适用）
- 注意事项

每个要点都必须标注法规来源，例如：
- 根据《xxx规定》第x条，应当...

**回答:**
"""

        return prompt

    def _parse_gemini_response(self, response_text: str, request: GeminiRequest) -> Dict[str, Any]:
        """Parse Gemini response into structured format."""
        try:
            # Basic parsing - extract answer and structure it
            answer_zh = response_text.strip()

            # Extract potential citations (basic implementation)
            citations = self._extract_citations_from_text(answer_zh, request)

            # Create sections from answer
            sections = self._structure_answer_sections(answer_zh)

            return {
                "answer_zh": answer_zh,
                "citations": citations,
                "sections": sections,
                "confidence_score": 0.8,  # Placeholder - could be improved
                "grounding_score": 0.7   # Placeholder - could be improved
            }

        except Exception as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            return {
                "answer_zh": "抱歉，我无法生成有效的回答。",
                "citations": [],
                "sections": [],
                "confidence_score": 0.0,
                "grounding_score": 0.0
            }

    def _extract_citations_from_text(self, text: str, request: GeminiRequest) -> List[Dict[str, Any]]:
        """Extract citation references from generated text."""
        citations = []
        doc_structure = request.document_structure

        # Look for patterns like "《xxx》第x条" or "根据xxx规定"
        citation_patterns = [
            r"《([^》]+)》",
            r"根据([^\n\r，。]+?)第?[一二三四五六七八九十\d]+条",
            r"([^\n\r，。]+?)第?[一二三四五六七八九十\d]+条"
        ]

        for pattern in citation_patterns:
            import re
            matches = re.findall(pattern, text)
            for match in matches:
                # Create citation entry
                citation = {
                    "citation_id": f"gemini_{len(citations) + 1}",
                    "title": match.strip(),
                    "url": doc_structure.url,
                    "effective_date": doc_structure.metadata.get("effective_date"),
                    "score": 0.8
                }
                citations.append(citation)

        return citations[:request.max_citations]

    def _structure_answer_sections(self, answer_text: str) -> List[Dict[str, Any]]:
        """Structure the answer into logical sections."""
        sections = []

        # Split by common section indicators
        section_patterns = [
            (r"核心要点[：:]", "核心要点"),
            (r"具体要求[：:]", "具体要求"),
            (r"实施步骤[：:]", "实施步骤"),
            (r"注意事项[：:]", "注意事项"),
            (r"操作指南[：:]", "操作指南")
        ]

        current_section = {"title": "回答", "bullets": []}

        lines = answer_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line starts a new section
            section_started = False
            for pattern, section_title in section_patterns:
                import re
                if re.match(pattern, line):
                    if current_section["bullets"]:
                        sections.append(current_section)
                    current_section = {"title": section_title, "bullets": []}
                    section_started = True
                    break

            if not section_started:
                # Add as bullet point
                if line.startswith('- ') or line.startswith('• ') or line.startswith('1.'):
                    current_section["bullets"].append(line)
                elif len(line) > 10:  # Substantial content
                    current_section["bullets"].append(f"- {line}")

        # Add final section
        if current_section["bullets"]:
            sections.append(current_section)

        return sections

    async def health_check(self) -> Dict[str, Any]:
        """Check Gemini API connectivity and health."""
        try:
            # Simple health check
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self.model.generate_content,
                "Hello"
            )

            return {
                "status": "healthy",
                "model": self.config.model,
                "response_time_ms": 0
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "model": self.config.model
            }



