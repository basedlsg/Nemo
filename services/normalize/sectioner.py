"""PR3: Minimal Sectioner - Chinese document section splitting and re-ranking

Splits Chinese government documents by headings and provides section-level relevance scoring.
"""

import re
from typing import List, Dict, Any, Tuple

# Chinese document section patterns
SECTION_RE = re.compile(r"^(第[一二三四五六七八九十百]+[章节]|第?\d+条|附录[一二三四]|目[ \t]*录)[\s　]*", re.MULTILINE)


def split_into_sections(text: str) -> List[Dict[str, Any]]:
    """
    Split Chinese document text into sections based on headings.

    Args:
        text: Document text to split

    Returns:
        List of sections with id, heading, and text
    """
    if not text:
        return []

    sections = []
    last_end = 0

    # Find all section headings
    for match in SECTION_RE.finditer(text):
        # Add content before this section if it exists
        if match.start() > last_end:
            content = text[last_end:match.start()].strip()
            if content:
                if sections and sections[-1]["text"] == "":
                    # Merge with previous empty section
                    sections[-1]["text"] = content
                else:
                    # Create new section for content before heading
                    sections.append({
                        "section_id": f"s{len(sections)}",
                        "heading": "前言/摘要",
                        "text": content
                    })

        # Add the section with heading
        sections.append({
            "section_id": f"s{len(sections)}",
            "heading": match.group(0).strip(),
            "text": ""
        })

        last_end = match.end()

    # Add remaining content after last heading
    if last_end < len(text):
        content = text[last_end:].strip()
        if content:
            if sections and sections[-1]["text"] == "":
                # Merge with last empty section
                sections[-1]["text"] = content
            else:
                # Create new section for trailing content
                sections.append({
                    "section_id": f"s{len(sections)}",
                    "heading": "正文",
                    "text": content
                })

    # Remove empty sections
    return [s for s in sections if s["text"].strip()]


def score_text(query: str, text: str) -> float:
    """
    Score text relevance using simple BM25-like approach.

    Args:
        query: Search query
        text: Text to score

    Returns:
        Relevance score
    """
    if not query or not text:
        return 0.0

    # Simple keyword matching with Chinese tokenization
    query_terms = set(_tokenize_chinese(query.lower()))
    text_terms = set(_tokenize_chinese(text.lower()))

    # Calculate term frequency and inverse document frequency
    matches = query_terms.intersection(text_terms)

    if not matches:
        return 0.0

    # Simple scoring: number of matches + length bonus for longer matches
    base_score = len(matches)

    # Bonus for exact phrase matches
    exact_matches = 0
    for term in query_terms:
        if term in text.lower():
            exact_matches += 1

    # Bonus for longer matching terms (likely more specific)
    length_bonus = sum(len(term) * 0.1 for term in matches if len(term) > 1)

    return base_score + exact_matches * 0.5 + length_bonus


def _tokenize_chinese(text: str) -> List[str]:
    """
    Simple Chinese text tokenization.

    Args:
        text: Text to tokenize

    Returns:
        List of tokens
    """
    if not text:
        return []

    # Remove punctuation and split by spaces/Chinese characters
    text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)

    # Split by whitespace and Chinese character boundaries
    tokens = []
    current_token = ""

    for char in text:
        if char.isspace():
            if current_token:
                tokens.append(current_token)
                current_token = ""
        elif '\u4e00' <= char <= '\u9fff':  # Chinese character
            if current_token:
                tokens.append(current_token)
            tokens.append(char)
            current_token = ""
        else:  # English/number
            current_token += char

    if current_token:
        tokens.append(current_token)

    return [t for t in tokens if t.strip()]


def rank_sections(query: str, doc_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Split document into sections and rank them by relevance to query.

    Args:
        query: Search query
        doc_text: Full document text
        top_k: Number of top sections to return

    Returns:
        Top-k most relevant sections
    """
    # Split document into sections
    sections = split_into_sections(doc_text)

    if not sections:
        return []

    # Score each section
    scored_sections = []
    for section in sections:
        score = score_text(query, section["text"])
        scored_sections.append((score, section))

    # Sort by score descending
    scored_sections.sort(key=lambda x: x[0], reverse=True)

    # Return top-k sections
    return [section for _, section in scored_sections[:top_k]]


def extract_section_text(sections: List[Dict[str, Any]], section_ids: List[str]) -> str:
    """
    Extract text from specific sections by ID.

    Args:
        sections: List of all sections
        section_ids: IDs of sections to extract

    Returns:
        Combined text from specified sections
    """
    section_map = {s["section_id"]: s for s in sections}

    extracted_text = []
    for section_id in section_ids:
        if section_id in section_map:
            section = section_map[section_id]
            extracted_text.append(f"{section['heading']}\n{section['text']}")

    return "\n\n".join(extracted_text)


def validate_section_references(sections: List[Dict[str, Any]], referenced_ids: List[str]) -> List[str]:
    """
    Validate that referenced section IDs exist.

    Args:
        sections: List of available sections
        referenced_ids: IDs that should be referenced

    Returns:
        List of valid section IDs
    """
    available_ids = {s["section_id"] for s in sections}
    return [sid for sid in referenced_ids if sid in available_ids]


# Example usage and testing functions
def _demo_sectioner():
    """Demo function for testing the sectioner."""
    sample_doc = """
    广东省光伏发电管理办法

    第一章 总则

    第一条 为规范广东省光伏发电项目管理，制定本办法。

    第二条 本办法适用于广东省行政区域内的光伏发电项目。

    第二章 项目申报

    第三条 项目申报应提交以下材料：
    （一）项目可行性研究报告；
    （二）项目用地证明文件；
    （三）电网接入意见书。

    第四条 申报时间为每年3月1日至3月31日。

    第三章 并网验收

    第五条 并网验收应由电网企业组织进行。

    第六条 验收合格后，项目方可并网发电。

    附录一 申报表格

    这是申报表格的内容示例。

    附录二 验收标准

    验收标准详细内容。
    """

    print("=== Document Sectioning Demo ===")
    sections = split_into_sections(sample_doc)
    print(f"Split into {len(sections)} sections:")

    for i, section in enumerate(sections):
        print(f"\nSection {i+1}:")
        print(f"ID: {section['section_id']}")
        print(f"Heading: {section['heading']}")
        print(f"Text preview: {section['text'][:100]}...")

    # Test ranking
    query = "光伏项目申报材料"
    ranked = rank_sections(query, sample_doc, top_k=2)
    print(f"\n=== Top 2 sections for query '{query}' ===")
    for i, section in enumerate(ranked):
        score = score_text(query, section["text"])
        print(".3f")
        print(f"Preview: {section['text'][:100]}...")


if __name__ == "__main__":
    _demo_sectioner()
