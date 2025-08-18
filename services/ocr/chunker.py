"""Text chunking and clause segmentation for Chinese energy regulation documents."""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4

from .schemas import ChunkData

logger = logging.getLogger(__name__)

# Default chunking parameters
DEFAULT_MAX_TOKENS = 800
DEFAULT_OVERLAP_TOKENS = 100
MIN_CHUNK_SIZE = 50


def estimate_token_count(text: str) -> int:
    """
    Estimate token count for Chinese text.
    
    Rough approximation: 1 Chinese character ≈ 1.5 tokens, 1 English word ≈ 1.3 tokens
    """
    if not text:
        return 0
    
    # Count Chinese characters
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    
    # Count English words (rough approximation)
    english_text = re.sub(r'[\u4e00-\u9fff]', '', text)
    english_words = len(re.findall(r'\b\w+\b', english_text))
    
    # Count numbers and punctuation
    other_chars = len(text) - chinese_chars - len(english_text.replace(' ', ''))
    
    # Estimate tokens
    estimated_tokens = int(chinese_chars * 1.5 + english_words * 1.3 + other_chars * 0.5)
    
    return max(1, estimated_tokens)


def split_into_clauses(paragraphs: List[str]) -> List[str]:
    """
    Split paragraphs into atomic clauses suitable for citation.
    
    Focuses on Chinese legal/regulatory text structure.
    """
    if not paragraphs:
        return []
    
    clauses = []
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
        
        # Split by Chinese sentence endings and legal structure markers
        clause_splits = _split_paragraph_into_clauses(paragraph)
        
        for clause in clause_splits:
            clause = clause.strip()
            if clause and len(clause) >= MIN_CHUNK_SIZE:
                clauses.append(clause)
    
    return clauses


def _split_paragraph_into_clauses(paragraph: str) -> List[str]:
    """Split a single paragraph into clauses based on Chinese legal text patterns."""
    
    # Patterns for splitting clauses (in order of priority)
    split_patterns = [
        # Article/section numbers: 第一条、第二条
        r'(第[一二三四五六七八九十百千万]+条)',
        
        # Numbered items: (一)、(二)、1.、2.
        r'([（(][一二三四五六七八九十百千万\d]+[）)])',
        r'(\d+[\.、])',
        
        # Chinese sentence endings
        r'([。！？；])',
        
        # Subsection markers
        r'([：:](?=\s*[（(一二三四五六七八九十\d]))',
        
        # Legal conjunctions that often start new clauses
        r'((?:同时|另外|此外|其中|包括|具体|特别|尤其)[，,]?)',
    ]
    
    # Start with the full paragraph
    current_splits = [paragraph]
    
    # Apply each split pattern
    for pattern in split_patterns:
        new_splits = []
        
        for text in current_splits:
            # Split by pattern but keep the delimiter
            parts = re.split(f'({pattern})', text)
            
            # Rejoin delimiters with following text
            rejoined = []
            i = 0
            while i < len(parts):
                if i + 1 < len(parts) and re.match(pattern, parts[i + 1]):
                    # This is text before a delimiter
                    if parts[i].strip():
                        rejoined.append(parts[i].strip())
                    # Combine delimiter with following text
                    if i + 2 < len(parts):
                        rejoined.append((parts[i + 1] + parts[i + 2]).strip())
                        i += 3
                    else:
                        rejoined.append(parts[i + 1].strip())
                        i += 2
                else:
                    if parts[i].strip():
                        rejoined.append(parts[i].strip())
                    i += 1
            
            new_splits.extend(rejoined)
        
        current_splits = [s for s in new_splits if s.strip()]
    
    return current_splits


def create_sliding_windows(
    clauses: List[str],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS
) -> List[ChunkData]:
    """
    Create sliding window chunks from clauses with specified overlap.
    """
    if not clauses:
        return []
    
    chunks = []
    current_chunk_clauses = []
    current_token_count = 0
    
    i = 0
    while i < len(clauses):
        clause = clauses[i]
        clause_tokens = estimate_token_count(clause)
        
        # If adding this clause would exceed the limit
        if current_token_count + clause_tokens > max_tokens and current_chunk_clauses:
            # Create chunk from current clauses
            chunk_content = '\n'.join(current_chunk_clauses)
            chunk = ChunkData(
                chunk_id=str(uuid4()),
                content=chunk_content,
                start_char=0,  # Will be calculated later if needed
                end_char=len(chunk_content),
                token_count=current_token_count,
                clause_type=_detect_clause_type(chunk_content)
            )
            chunks.append(chunk)
            
            # Create overlap for next chunk
            overlap_clauses, overlap_tokens = _create_overlap(
                current_chunk_clauses, overlap_tokens
            )
            
            current_chunk_clauses = overlap_clauses
            current_token_count = overlap_tokens
        else:
            # Add clause to current chunk
            current_chunk_clauses.append(clause)
            current_token_count += clause_tokens
            i += 1
    
    # Add final chunk if there are remaining clauses
    if current_chunk_clauses:
        chunk_content = '\n'.join(current_chunk_clauses)
        chunk = ChunkData(
            chunk_id=str(uuid4()),
            content=chunk_content,
            start_char=0,
            end_char=len(chunk_content),
            token_count=current_token_count,
            clause_type=_detect_clause_type(chunk_content)
        )
        chunks.append(chunk)
    
    return chunks


def _create_overlap(clauses: List[str], target_overlap_tokens: int) -> Tuple[List[str], int]:
    """Create overlap clauses for the next chunk."""
    if not clauses:
        return [], 0
    
    overlap_clauses = []
    overlap_tokens = 0
    
    # Start from the end and work backwards
    for clause in reversed(clauses):
        clause_tokens = estimate_token_count(clause)
        
        if overlap_tokens + clause_tokens <= target_overlap_tokens:
            overlap_clauses.insert(0, clause)
            overlap_tokens += clause_tokens
        else:
            break
    
    return overlap_clauses, overlap_tokens


def _detect_clause_type(content: str) -> Optional[str]:
    """Detect the type of clause based on content patterns."""
    
    # Article/section
    if re.search(r'第[一二三四五六七八九十百千万]+条', content):
        return "article"
    
    # Numbered item
    if re.search(r'^[（(][一二三四五六七八九十百千万\d]+[）)]', content.strip()):
        return "numbered_item"
    
    # Definition
    if re.search(r'是指|定义为|指的是', content):
        return "definition"
    
    # Requirement/obligation
    if re.search(r'应当|必须|应该|需要|要求', content):
        return "requirement"
    
    # Prohibition
    if re.search(r'不得|禁止|不允许|不可', content):
        return "prohibition"
    
    # Procedure/process
    if re.search(r'程序|流程|步骤|办理', content):
        return "procedure"
    
    # Standard/specification
    if re.search(r'标准|规范|技术要求|参数', content):
        return "standard"
    
    # Table content
    if '|' in content and content.count('|') >= 4:
        return "table"
    
    return "general"


def optimize_chunks_for_citation(chunks: List[ChunkData]) -> List[ChunkData]:
    """
    Optimize chunks for better citation quality.
    
    - Merge very short chunks
    - Split overly long chunks
    - Ensure each chunk has meaningful content
    """
    if not chunks:
        return []
    
    optimized = []
    
    i = 0
    while i < len(chunks):
        current_chunk = chunks[i]
        
        # If chunk is too short, try to merge with next
        if (current_chunk.token_count < MIN_CHUNK_SIZE and 
            i + 1 < len(chunks) and 
            current_chunk.token_count + chunks[i + 1].token_count <= DEFAULT_MAX_TOKENS):
            
            next_chunk = chunks[i + 1]
            merged_content = current_chunk.content + '\n' + next_chunk.content
            
            merged_chunk = ChunkData(
                chunk_id=str(uuid4()),
                content=merged_content,
                start_char=current_chunk.start_char,
                end_char=next_chunk.end_char,
                token_count=current_chunk.token_count + next_chunk.token_count,
                clause_type=current_chunk.clause_type or next_chunk.clause_type
            )
            
            optimized.append(merged_chunk)
            i += 2  # Skip next chunk as it's been merged
        else:
            optimized.append(current_chunk)
            i += 1
    
    return optimized


def chunk_document_content(
    paragraphs: List[str],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS
) -> List[ChunkData]:
    """
    Main function to chunk document content into citation-ready pieces.
    
    Args:
        paragraphs: List of normalized paragraphs
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Overlap between chunks
        
    Returns:
        List of ChunkData objects ready for citation
    """
    try:
        logger.info(f"Chunking {len(paragraphs)} paragraphs with max_tokens={max_tokens}, overlap={overlap_tokens}")
        
        # Step 1: Split paragraphs into atomic clauses
        clauses = split_into_clauses(paragraphs)
        logger.info(f"Split into {len(clauses)} clauses")
        
        # Step 2: Create sliding window chunks
        chunks = create_sliding_windows(clauses, max_tokens, overlap_tokens)
        logger.info(f"Created {len(chunks)} initial chunks")
        
        # Step 3: Optimize chunks for citation quality
        optimized_chunks = optimize_chunks_for_citation(chunks)
        logger.info(f"Optimized to {len(optimized_chunks)} final chunks")
        
        # Step 4: Calculate character positions
        _calculate_character_positions(optimized_chunks, paragraphs)
        
        return optimized_chunks
        
    except Exception as e:
        logger.error(f"Error chunking document content: {e}")
        return []


def _calculate_character_positions(chunks: List[ChunkData], original_paragraphs: List[str]) -> None:
    """Calculate start and end character positions for chunks in original text."""
    full_text = '\n'.join(original_paragraphs)
    
    for chunk in chunks:
        # Find the position of chunk content in full text
        start_pos = full_text.find(chunk.content[:100])  # Use first 100 chars for matching
        
        if start_pos >= 0:
            chunk.start_char = start_pos
            chunk.end_char = start_pos + len(chunk.content)
        else:
            # Fallback: approximate position
            chunk.start_char = 0
            chunk.end_char = len(chunk.content)


def analyze_chunking_quality(chunks: List[ChunkData]) -> Dict[str, Any]:
    """Analyze the quality of chunking results."""
    if not chunks:
        return {"error": "No chunks to analyze"}
    
    token_counts = [chunk.token_count for chunk in chunks]
    clause_types = [chunk.clause_type for chunk in chunks if chunk.clause_type]
    
    analysis = {
        "total_chunks": len(chunks),
        "avg_tokens_per_chunk": sum(token_counts) / len(token_counts),
        "min_tokens": min(token_counts),
        "max_tokens": max(token_counts),
        "chunks_under_min": sum(1 for t in token_counts if t < MIN_CHUNK_SIZE),
        "chunks_over_max": sum(1 for t in token_counts if t > DEFAULT_MAX_TOKENS),
        "clause_type_distribution": {},
        "total_content_length": sum(len(chunk.content) for chunk in chunks)
    }
    
    # Calculate clause type distribution
    for clause_type in set(clause_types):
        analysis["clause_type_distribution"][clause_type] = clause_types.count(clause_type)
    
    return analysis