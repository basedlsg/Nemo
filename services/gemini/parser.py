"""Hierarchical document parser for structured content extraction."""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .schemas import DocumentStructure, DocumentSection

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Document chunk with metadata."""
    content: str
    chunk_type: str
    position: int
    confidence: float
    metadata: Dict[str, Any]


class HierarchicalDocumentParser:
    """Parser that creates hierarchical document structures from chunks."""

    def __init__(self):
        """Initialize document parser."""
        self.logger = logging.getLogger(__name__)

    def parse_document_structure(
        self,
        title: str,
        url: str,
        chunks: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> DocumentStructure:
        """Parse document chunks into hierarchical structure."""
        try:
            # Convert chunks to structured format
            structured_chunks = self._convert_chunks(chunks)

            # Group chunks by type and hierarchy
            sections = self._build_hierarchy(structured_chunks)

            # Create document structure
            doc_structure = DocumentStructure(
                title=title,
                url=url,
                sections=sections,
                tables=[],  # Could be extracted from chunks if available
                metadata=metadata or {}
            )

            logger.info(f"Parsed document structure: {len(sections)} sections from {len(chunks)} chunks")
            return doc_structure

        except Exception as e:
            logger.error(f"Failed to parse document structure: {e}")
            return DocumentStructure(
                title=title,
                url=url,
                sections=[],
                tables=[],
                metadata=metadata or {}
            )

    def _convert_chunks(self, chunks: List[Dict[str, Any]]) -> List[DocumentChunk]:
        """Convert raw chunks to structured format."""
        structured_chunks = []

        for i, chunk in enumerate(chunks):
            # Extract chunk information
            content = chunk.get('content', '')
            chunk_type = chunk.get('chunk_type', 'general')
            position = chunk.get('position', i)
            confidence = chunk.get('confidence', 1.0)
            metadata = chunk.get('metadata', {})

            structured_chunk = DocumentChunk(
                content=content,
                chunk_type=chunk_type,
                position=position,
                confidence=confidence,
                metadata=metadata
            )

            structured_chunks.append(structured_chunk)

        return structured_chunks

    def _build_hierarchy(self, chunks: List[DocumentChunk]) -> List[DocumentSection]:
        """Build hierarchical sections from chunks."""
        sections = []

        # Group chunks by type
        chunk_groups = self._group_chunks_by_type(chunks)

        # Convert each group to sections
        for group_type, group_chunks in chunk_groups.items():
            if group_chunks:
                section = self._create_section_from_chunks(group_type, group_chunks)
                if section:
                    sections.append(section)

        # Sort sections by position
        sections.sort(key=lambda x: getattr(x, 'start_position', 0))

        return sections

    def _group_chunks_by_type(self, chunks: List[DocumentChunk]) -> Dict[str, List[DocumentChunk]]:
        """Group chunks by their type."""
        groups = {}

        for chunk in chunks:
            chunk_type = chunk.chunk_type

            if chunk_type not in groups:
                groups[chunk_type] = []

            groups[chunk_type].append(chunk)

        return groups

    def _create_section_from_chunks(
        self,
        section_type: str,
        chunks: List[DocumentChunk]
    ) -> Optional[DocumentSection]:
        """Create a document section from chunks."""
        if not chunks:
            return None

        try:
            # Combine chunk contents
            combined_content = '\n\n'.join(chunk.content for chunk in chunks)

            # Sort chunks by position
            chunks.sort(key=lambda x: x.position)

            # Create section title based on type
            section_title = self._get_section_title(section_type, chunks)

            # Calculate position range
            start_position = min(chunk.position for chunk in chunks)
            end_position = max(chunk.position + len(chunk.content) for chunk in chunks)

            # Calculate average confidence
            avg_confidence = sum(chunk.confidence for chunk in chunks) / len(chunks)

            return DocumentSection(
                section_type=section_type,
                title=section_title,
                content=combined_content,
                subsections=[],  # Could be nested if needed
                start_position=start_position,
                end_position=end_position,
                confidence=avg_confidence
            )

        except Exception as e:
            logger.error(f"Failed to create section from chunks: {e}")
            return None

    def _get_section_title(self, section_type: str, chunks: List[DocumentChunk]) -> str:
        """Generate section title based on type and content."""
        # Use first chunk's content to generate title
        if chunks:
            first_chunk = chunks[0]
            content_preview = first_chunk.content[:100].strip()

            # Extract potential titles from content
            title_patterns = [
                r'^第[一二三四五六七八九十百千万\d]+条[：:]*\s*(.+)$',  # Article numbers
                r'^[（(][一二三四五六七八九十百千万\d]+[）)]\s*(.+)$',  # Numbered items
                r'^(.{1,50})[：:]\s*$',  # Title followed by colon
            ]

            import re
            for pattern in title_patterns:
                match = re.match(pattern, content_preview, re.MULTILINE)
                if match:
                    title = match.group(1).strip()
                    if title:
                        return title

        # Fallback to section type
        type_titles = {
            'article': '法规条款',
            'requirement': '具体要求',
            'procedure': '操作流程',
            'definition': '定义说明',
            'standard': '技术标准',
            'prohibition': '禁止规定',
            'table': '数据表格',
            'general': '一般规定'
        }

        return type_titles.get(section_type, f"{section_type}内容")

    def extract_key_sections(
        self,
        doc_structure: DocumentStructure,
        query_keywords: List[str],
        max_sections: int = 5
    ) -> List[DocumentSection]:
        """Extract most relevant sections based on query keywords."""
        relevant_sections = []

        for section in doc_structure.sections:
            relevance_score = self._calculate_section_relevance(section, query_keywords)

            if relevance_score > 0:
                relevant_sections.append((section, relevance_score))

        # Sort by relevance and take top sections
        relevant_sections.sort(key=lambda x: x[1], reverse=True)
        top_sections = [section for section, score in relevant_sections[:max_sections]]

        logger.info(f"Extracted {len(top_sections)} key sections from {len(doc_structure.sections)} total")
        return top_sections

    def _calculate_section_relevance(
        self,
        section: DocumentSection,
        keywords: List[str]
    ) -> float:
        """Calculate relevance score for a section based on keywords."""
        score = 0.0
        content = f"{section.title} {section.content}".lower()

        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in content:
                # Boost score based on keyword importance
                if section.section_type in ['requirement', 'procedure', 'article']:
                    score += 2.0  # Higher weight for important section types
                else:
                    score += 1.0

                # Boost for title matches
                if keyword_lower in section.title.lower():
                    score += 1.0

        return score



