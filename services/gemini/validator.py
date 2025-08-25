"""Answer validation and grounding for Gemini-generated responses."""

import logging
import re
from typing import List, Dict, Any, Set
from difflib import SequenceMatcher

from .schemas import GroundingResult, AnswerValidationResult

logger = logging.getLogger(__name__)


class AnswerValidator:
    """Validates Gemini-generated answers for grounding and accuracy."""

    def __init__(self, grounding_threshold: float = 0.7):
        """Initialize answer validator."""
        self.grounding_threshold = grounding_threshold

    def validate_answer(
        self,
        answer: str,
        source_documents: List[Dict[str, Any]],
        citations: List[Dict[str, Any]]
    ) -> AnswerValidationResult:
        """Validate answer for grounding and accuracy."""
        try:
            # Perform grounding validation
            grounding = self._validate_grounding(answer, source_documents)

            # Calculate overall score
            overall_score = self._calculate_overall_score(grounding, citations)

            # Determine if answer is valid
            is_valid = overall_score >= self.grounding_threshold

            # Generate issues and recommendations
            issues = self._identify_issues(answer, grounding, citations)
            recommendations = self._generate_recommendations(issues, grounding)

            return AnswerValidationResult(
                grounding=grounding,
                overall_score=overall_score,
                is_valid=is_valid,
                issues=issues,
                recommendations=recommendations
            )

        except Exception as e:
            logger.error(f"Answer validation failed: {e}")
            return AnswerValidationResult(
                grounding=GroundingResult(is_grounded=False),
                overall_score=0.0,
                is_valid=False,
                issues=[f"Validation error: {str(e)}"],
                recommendations=["Retry with different parameters"]
            )

    def _validate_grounding(
        self,
        answer: str,
        source_documents: List[Dict[str, Any]]
    ) -> GroundingResult:
        """Validate that answer is grounded in source documents."""
        try:
            # Extract phrases from answer
            answer_phrases = self._extract_answer_phrases(answer)

            grounded_phrases = []
            ungrounded_phrases = []

            # Combine all source document content
            source_content = self._combine_source_content(source_documents)

            # Check each phrase against source content
            for phrase in answer_phrases:
                if self._is_phrase_grounded(phrase, source_content):
                    grounded_phrases.append(phrase)
                else:
                    ungrounded_phrases.append(phrase)

            # Calculate grounding metrics
            total_phrases = len(answer_phrases)
            grounded_count = len(grounded_phrases)

            grounding_score = grounded_count / total_phrases if total_phrases > 0 else 0.0
            is_grounded = grounding_score >= self.grounding_threshold

            return GroundingResult(
                is_grounded=is_grounded,
                grounding_score=grounding_score,
                grounded_phrases=grounded_phrases,
                ungrounded_phrases=ungrounded_phrases,
                citation_coverage=0.0,  # Will be calculated separately
                validation_details={
                    "total_phrases": total_phrases,
                    "grounded_count": grounded_count,
                    "source_documents": len(source_documents)
                }
            )

        except Exception as e:
            logger.error(f"Grounding validation failed: {e}")
            return GroundingResult(
                is_grounded=False,
                grounding_score=0.0,
                ungrounded_phrases=["Validation error"],
                validation_details={"error": str(e)}
            )

    def _extract_answer_phrases(self, answer: str) -> List[str]:
        """Extract meaningful phrases from answer for grounding validation."""
        # Split answer into sentences and key phrases
        sentences = re.split(r'[。！？；]', answer)

        phrases = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Extract noun phrases and key terms
            # Look for quoted content (direct citations)
            quoted_matches = re.findall(r'《([^》]+)》', sentence)
            phrases.extend(quoted_matches)

            # Look for specific regulatory terms
            regulatory_terms = re.findall(r'第[一二三四五六七八九十百千万\d]+条', sentence)
            phrases.extend(regulatory_terms)

            # Look for specific requirements
            requirement_terms = re.findall(r'应当|必须|不得|可以|需要', sentence)
            if requirement_terms:
                # Include the sentence containing requirements
                phrases.append(sentence)

        # Remove duplicates while preserving order
        seen = set()
        unique_phrases = []
        for phrase in phrases:
            if phrase not in seen:
                seen.add(phrase)
                unique_phrases.append(phrase)

        return unique_phrases

    def _combine_source_content(self, source_documents: List[Dict[str, Any]]) -> str:
        """Combine all source document content into searchable text."""
        combined_content = []

        for doc in source_documents:
            # Add title
            if doc.get('title'):
                combined_content.append(doc['title'])

            # Add body content
            if doc.get('body'):
                combined_content.append(doc['body'])

            # Add headings
            if doc.get('headings'):
                combined_content.append(doc['headings'])

            # Add any other text fields
            for key, value in doc.items():
                if isinstance(value, str) and key not in ['title', 'body', 'headings', 'url']:
                    combined_content.append(value)

        return '\n'.join(combined_content).lower()

    def _is_phrase_grounded(self, phrase: str, source_content: str) -> bool:
        """Check if a phrase is grounded in source content."""
        if not phrase or not source_content:
            return False

        phrase_lower = phrase.lower().strip()

        # Direct substring match
        if phrase_lower in source_content:
            return True

        # Fuzzy matching for slight variations
        words = phrase_lower.split()
        if len(words) > 2:
            # Check if most words appear in source
            matching_words = sum(1 for word in words if len(word) > 1 and word in source_content)
            if matching_words / len(words) >= 0.8:
                return True

        # Sequence matching for similar phrases
        # This is a simplified approach - could be enhanced
        return False

    def _calculate_overall_score(
        self,
        grounding: GroundingResult,
        citations: List[Dict[str, Any]]
    ) -> float:
        """Calculate overall answer quality score."""
        score = 0.0

        # Grounding score (70% weight)
        score += grounding.grounding_score * 0.7

        # Citation quality (20% weight)
        citation_score = min(len(citations) / 5.0, 1.0)  # Max score at 5 citations
        score += citation_score * 0.2

        # Citation diversity (10% weight)
        if citations:
            unique_sources = len(set(c.get('url', '') for c in citations))
            diversity_score = min(unique_sources / 3.0, 1.0)  # Max score at 3 sources
            score += diversity_score * 0.1

        return min(score, 1.0)

    def _identify_issues(
        self,
        answer: str,
        grounding: GroundingResult,
        citations: List[Dict[str, Any]]
    ) -> List[str]:
        """Identify validation issues."""
        issues = []

        # Grounding issues
        if not grounding.is_grounded:
            issues.append("Answer is not sufficiently grounded in source documents")

        if grounding.ungrounded_phrases:
            issues.append(f"Found {len(grounding.ungrounded_phrases)} ungrounded phrases")

        # Citation issues
        if not citations:
            issues.append("No citations provided in answer")

        if len(citations) > 10:
            issues.append("Too many citations - may indicate unfocused answer")

        # Content issues
        if len(answer) < 50:
            issues.append("Answer is too short")

        if len(answer) > 5000:
            issues.append("Answer is too long")

        return issues

    def _generate_recommendations(
        self,
        issues: List[str],
        grounding: GroundingResult
    ) -> List[str]:
        """Generate recommendations based on validation issues."""
        recommendations = []

        if not grounding.is_grounded:
            recommendations.append("Increase grounding threshold or provide more source documents")

        if grounding.ungrounded_phrases:
            recommendations.append("Review ungrounded phrases and verify against source documents")

        if not issues:
            recommendations.append("Answer quality is good - no changes needed")

        return recommendations

    def validate_citations_against_sources(
        self,
        citations: List[Dict[str, Any]],
        source_documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate that citations actually exist in source documents."""
        validation_results = {
            "valid_citations": 0,
            "invalid_citations": 0,
            "citation_details": []
        }

        source_urls = {doc.get('url', '') for doc in source_documents}

        for citation in citations:
            citation_url = citation.get('url', '')
            is_valid = citation_url in source_urls

            if is_valid:
                validation_results["valid_citations"] += 1
            else:
                validation_results["invalid_citations"] += 1

            validation_results["citation_details"].append({
                "citation_id": citation.get('citation_id', ''),
                "url": citation_url,
                "is_valid": is_valid
            })

        return validation_results



