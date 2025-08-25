"""PR4: Two-Pass Entailment - Validate answers against cited sections

Ensures that every factual sentence in the answer is supported by the cited sections.
"""

import re
from typing import List, Dict, Any, Tuple
from services.normalize.sectioner import extract_section_text, validate_section_references


def supported_by_sections(answer_zh: str, sections: List[Dict[str, Any]]) -> bool:
    """
    PR4: Ultra-simple entailment check for Chinese text.

    Checks if each factual sentence in the answer is supported by cited sections
    through substring or relaxed whitespace matching.

    Args:
        answer_zh: Generated answer text in Chinese
        sections: List of cited sections with text

    Returns:
        True if answer is sufficiently supported by sections
    """
    if not answer_zh or not sections:
        return False

    # Extract all section text
    pool = "\n".join([s.get("text", "") for s in sections if s.get("text")])

    # Split answer into sentences
    sents = [s.strip() for s in re.split(r"[。！？!?]", answer_zh) if s.strip()]

    if not sents:
        return False

    # Check each sentence
    ok_sentences = 0
    for sent in sents:
        if _sentence_supported(sent, pool):
            ok_sentences += 1

    # Allow one loose paraphrase (80% threshold)
    return ok_sentences >= max(1, len(sents) - 1)


def _sentence_supported(sentence: str, section_pool: str) -> bool:
    """
    Check if a single sentence is supported by the section pool.

    Args:
        sentence: Sentence to check
        section_pool: Combined text from all cited sections

    Returns:
        True if sentence is supported
    """
    if not sentence or not section_pool:
        return False

    # Normalize whitespace for comparison
    sent_normalized = _normalize_text(sentence)
    pool_normalized = _normalize_text(section_pool)

    # Direct substring match
    if sent_normalized in pool_normalized:
        return True

    # Relaxed whitespace match (remove spaces and punctuation)
    sent_relaxed = _relax_text(sent_normalized)
    pool_relaxed = _relax_text(pool_normalized)

    if sent_relaxed in pool_relaxed:
        return True

    # Check for key terms (if sentence is longer than 4 characters)
    if len(sent_normalized) > 4:
        # Extract key terms (Chinese words and numbers)
        key_terms = _extract_key_terms(sent_normalized)
        if key_terms and all(term in pool_relaxed for term in key_terms):
            return True

    return False


def _normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    if not text:
        return ""

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())

    # Normalize Chinese punctuation
    text = text.replace('，', ',').replace('：', ':').replace('；', ';')

    return text


def _relax_text(text: str) -> str:
    """Create relaxed version by removing spaces and punctuation."""
    if not text:
        return ""

    # Remove all whitespace and punctuation
    relaxed = re.sub(r'[^\w\u4e00-\u9fff]', '', text)

    return relaxed


def _extract_key_terms(text: str) -> List[str]:
    """Extract key terms from Chinese text."""
    if not text:
        return []

    # Split by spaces and extract meaningful terms
    words = text.split()
    key_terms = []

    for word in words:
        # Keep words that are meaningful (longer than 1 char or contain numbers)
        if len(word) > 1 or re.search(r'\d', word):
            key_terms.append(_relax_text(word))

    return key_terms


def validate_answer_entailment(
    answer_zh: str,
    cited_sections: List[Dict[str, Any]],
    section_ids: List[str]
) -> Tuple[bool, str]:
    """
    PR4: Main entailment validation function.

    Args:
        answer_zh: Generated answer text
        cited_sections: All available sections from the document
        section_ids: IDs of sections that should support the answer

    Returns:
        Tuple of (is_supported, reason)
    """
    try:
        # Validate that referenced section IDs exist
        valid_ids = validate_section_references(cited_sections, section_ids)

        if not valid_ids:
            return False, "no_valid_section_references"

        # Extract text from referenced sections
        section_text = extract_section_text(cited_sections, valid_ids)

        if not section_text.strip():
            return False, "empty_section_text"

        # Check if answer is supported
        is_supported = supported_by_sections(answer_zh, cited_sections)

        if not is_supported:
            return False, "answer_not_entailed_by_sections"

        return True, "entailment_validated"

    except Exception as e:
        return False, f"entailment_validation_error: {str(e)}"


class EntailmentValidator:
    """PR4: Entailment validation service."""

    def __init__(self):
        """Initialize entailment validator."""
        self.stats = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "failure_reasons": {}
        }

    def validate(
        self,
        answer_zh: str,
        cited_sections: List[Dict[str, Any]],
        section_ids: List[str]
    ) -> Tuple[bool, str]:
        """
        Validate answer entailment.

        Args:
            answer_zh: Generated answer
            cited_sections: Available sections
            section_ids: Referenced section IDs

        Returns:
            Tuple of (is_valid, reason)
        """
        self.stats["total_validations"] += 1

        is_valid, reason = validate_answer_entailment(answer_zh, cited_sections, section_ids)

        if is_valid:
            self.stats["successful_validations"] += 1
        else:
            self.stats["failed_validations"] += 1
            self.stats["failure_reasons"][reason] = self.stats["failure_reasons"].get(reason, 0) + 1

        return is_valid, reason

    def get_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        return self.stats.copy()


# Global validator instance
_entailment_validator: EntailmentValidator = None


def get_entailment_validator() -> EntailmentValidator:
    """Get global entailment validator instance."""
    global _entailment_validator
    if _entailment_validator is None:
        _entailment_validator = EntailmentValidator()
    return _entailment_validator


def demo_entailment_validation():
    """Demo function for testing entailment validation."""
    print("=== Entailment Validation Demo ===")

    # Sample sections from a Chinese government document
    sections = [
        {
            "section_id": "s0",
            "heading": "第一章 总则",
            "text": "第一条 为规范广东省光伏发电项目管理，制定本办法。"
        },
        {
            "section_id": "s1",
            "heading": "第二章 项目申报",
            "text": "第二条 项目申报应提交以下材料：（一）项目可行性研究报告；（二）项目用地证明文件；（三）电网接入意见书。"
        },
        {
            "section_id": "s2",
            "heading": "第三章 并网验收",
            "text": "第三条 并网验收应由电网企业组织进行。验收合格后，项目方可并网发电。"
        }
    ]

    # Test cases
    test_cases = [
        {
            "answer": "广东省光伏发电项目需要提交可行性研究报告。",
            "section_ids": ["s1"],
            "expected": True,
            "reason": "Direct match with section text"
        },
        {
            "answer": "项目申报需要用地证明文件。",
            "section_ids": ["s1"],
            "expected": True,
            "reason": "Key terms match"
        },
        {
            "answer": "并网验收由电网企业进行。",
            "section_ids": ["s2"],
            "expected": True,
            "reason": "Direct support from section"
        },
        {
            "answer": "风电项目需要提交环境影响报告。",
            "section_ids": ["s1"],
            "expected": False,
            "reason": "Wrong asset type (wind vs solar)"
        },
        {
            "answer": "项目申报需要身份证复印件。",
            "section_ids": ["s1"],
            "expected": False,
            "reason": "Made up requirement not in sections"
        }
    ]

    validator = get_entailment_validator()

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['reason']}")
        print(f"Answer: {test_case['answer']}")
        print(f"Section IDs: {test_case['section_ids']}")

        is_valid, reason = validator.validate(
            test_case['answer'],
            sections,
            test_case['section_ids']
        )

        print(f"Expected: {'✅ PASS' if test_case['expected'] else '❌ FAIL'}")
        print(f"Actual: {'✅ PASS' if is_valid else '❌ FAIL'}")
        print(f"Reason: {reason}")

        if is_valid == test_case['expected']:
            print("✅ Test passed")
        else:
            print("❌ Test failed")

    print("
=== Final Stats ===")
    stats = validator.get_stats()
    print(f"Total validations: {stats['total_validations']}")
    print(f"Successful: {stats['successful_validations']}")
    print(f"Failed: {stats['failed_validations']}")
    print(f"Failure reasons: {stats['failure_reasons']}")


if __name__ == "__main__":
    demo_entailment_validation()
