# Improved retrieval system with RRF fusion and metadata-first filtering
# Implements two-stage recall: keyword + dense, then re-rank

import logging
from collections import defaultdict
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import math

logger = logging.getLogger(__name__)

class RetrievalSystem:
    """Two-stage retrieval system for Chinese energy regulations."""

    def __init__(self, db_connection):
        self.db = db_connection
        self.refusal_threshold = 2.0  # Configurable threshold for refusal

    def retrieve_documents(self, query, expanded_terms, hard_filters) -> Dict[str, Any]:
        """
        Main retrieval pipeline:
        1. Apply hard filters (metadata-first)
        2. Two-stage recall (keyword + dense)
        3. RRF fusion
        4. Final re-ranking with diagnostics
        """
        try:
            # Stage 1: Keyword recall
            keyword_results = self._keyword_recall(expanded_terms, hard_filters)

            # Stage 2: Dense recall
            dense_results = self._dense_recall(query.question, hard_filters)

            # Stage 3: RRF fusion
            fused_results = self._rrf_fusion([keyword_results, dense_results], k=60)

            # Stage 4: Final scoring with diagnostics
            scored_results = self._final_scoring(fused_results, expanded_terms, hard_filters)

            # Stage 5: Apply refusal threshold
            final_results, should_refuse = self._apply_refusal_threshold(scored_results)

            return {
                "results": final_results,
                "should_refuse": should_refuse,
                "total_candidates": len(scored_results),
                "filters_applied": hard_filters
            }

        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            return {
                "results": [],
                "should_refuse": True,
                "total_candidates": 0,
                "filters_applied": hard_filters,
                "error": str(e)
            }

    def _keyword_recall(self, expanded_terms, filters) -> List[Tuple[str, float]]:
        """Keyword-based recall using trigram similarity on title/headings/文号."""
        try:
            # Build search terms from expanded query
            search_terms = set()
            search_terms.update(expanded_terms.get("provinces", []))
            search_terms.update(expanded_terms.get("doc_classes", []))
            search_terms.update(expanded_terms.get("assets", []))

            # Build SQL query with filters
            query_parts = []
            params = []

            # Base query
            sql = """
                SELECT id, title, headings, wenhao
                FROM citations
                WHERE 1=1
            """

            # Apply hard filters
            if filters.get("province_normalized"):
                sql += " AND province_normalized = ANY(%s)"
                params.append(filters["province_normalized"])

            if filters.get("doc_class_normalized"):
                sql += " AND doc_class_normalized = ANY(%s)"
                params.append(filters["doc_class_normalized"])

            if filters.get("status"):
                sql += " AND status = ANY(%s)"
                params.append(filters["status"])

            if filters.get("domain_in_allowlist"):
                # Assuming we have a domain allowlist table or config
                sql += " AND domain IN (SELECT domain FROM allowlist_domains)"

            # Add date filter (last 6 years by default)
            cutoff_date = datetime.now() - timedelta(days=365*6)
            sql += " AND (effective_date >= %s OR publish_date >= %s)"
            params.extend([cutoff_date, cutoff_date])

            # Add keyword similarity scoring
            term_conditions = []
            for term in search_terms:
                term_conditions.append(f"""
                    (COALESCE(similarity(title, %s), 0) +
                     COALESCE(similarity(headings, %s), 0) +
                     CASE WHEN wenhao ILIKE %s THEN 1.0 ELSE 0 END)
                """)
                params.extend([term, term, f"%{term}%"])

            if term_conditions:
                sql += f" ORDER BY ({' + '.join(term_conditions)}) DESC"
            else:
                sql += " ORDER BY effective_date DESC"

            sql += " LIMIT 50"

            # Execute query
            cursor = self.db.cursor()
            cursor.execute(sql, params)
            results = cursor.fetchall()

            # Convert to (id, score) tuples
            scored_results = []
            for row in results:
                doc_id, title, headings, wenhao = row
                # Simple scoring based on matches
                score = 0.0
                if title:
                    for term in search_terms:
                        if term.lower() in title.lower():
                            score += 0.4
                if headings:
                    for term in search_terms:
                        if term.lower() in headings.lower():
                            score += 0.3
                if wenhao and any(term.lower() in wenhao.lower() for term in search_terms):
                    score += 0.3
                scored_results.append((doc_id, score))

            return scored_results

        except Exception as e:
            logger.error(f"Keyword recall error: {e}")
            return []

    def _dense_recall(self, question: str, filters) -> List[Tuple[str, float]]:
        """Dense retrieval using vector similarity."""
        try:
            # Generate embedding for the question (placeholder - integrate with actual embedding service)
            question_embedding = self._generate_embedding(question)

            # Build SQL query with filters
            sql = """
                SELECT id, 1 / (1 + (embedding <-> %s::vector)) as similarity
                FROM citations
                WHERE 1=1
            """
            params = [question_embedding]

            # Apply same filters as keyword search
            if filters.get("province_normalized"):
                sql += " AND province_normalized = ANY(%s)"
                params.append(filters["province_normalized"])

            if filters.get("doc_class_normalized"):
                sql += " AND doc_class_normalized = ANY(%s)"
                params.append(filters["doc_class_normalized"])

            if filters.get("status"):
                sql += " AND status = ANY(%s)"
                params.append(filters["status"])

            sql += " ORDER BY embedding <-> %s::vector LIMIT 50"
            params.append(question_embedding)

            cursor = self.db.cursor()
            cursor.execute(sql, params)
            results = cursor.fetchall()

            return [(row[0], float(row[1])) for row in results]

        except Exception as e:
            logger.error(f"Dense recall error: {e}")
            return []

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text (placeholder implementation)."""
        # TODO: Integrate with actual embedding service (BGE-m3, jina-embeddings-zh, etc.)
        # For now, return a dummy embedding
        import random
        return [random.random() for _ in range(1536)]

    def _rrf_fusion(self, result_lists: List[List[Tuple[str, float]]], k=60) -> Dict[str, float]:
        """Reciprocal Rank Fusion to combine multiple retrieval results."""
        scores = defaultdict(float)

        for result_list in result_lists:
            for rank, (doc_id, score) in enumerate(result_list, 1):
                # RRF score: sum of 1/(k + rank) for each list
                scores[doc_id] += 1.0 / (k + rank)

        return dict(scores)

    def _final_scoring(self, fused_scores: Dict[str, float], expanded_terms, filters) -> List[Dict]:
        """Final scoring with diagnostics and metadata."""
        try:
            if not fused_scores:
                return []

            # Get document details
            doc_ids = list(fused_scores.keys())
            placeholders = ','.join(['%s'] * len(doc_ids))

            sql = """
                SELECT id, title, headings, body, wenhao, agency, publish_date, effective_date, status,
                       province_normalized, doc_class_normalized, url, domain
                FROM citations
                WHERE id IN ({})
            """.format(placeholders)

            cursor = self.db.cursor()
            cursor.execute(sql, doc_ids)
            docs = cursor.fetchall()

            scored_docs = []
            for row in docs:
                doc = dict(zip([
                    'id', 'title', 'headings', 'body', 'wenhao', 'agency',
                    'publish_date', 'effective_date', 'status', 'province_normalized',
                    'doc_class_normalized', 'url', 'domain'
                ], row))

                # Calculate final score
                final_score = self._calculate_final_score(doc, fused_scores[doc['id']], expanded_terms)

                # Build diagnostics
                diagnostics = self._build_diagnostics(doc, expanded_terms)

                scored_docs.append({
                    "id": doc['id'],
                    "title": doc['title'] or "",
                    "url": doc['url'] or "",
                    "score": final_score,
                    "metadata": {
                        "wenhao": doc['wenhao'],
                        "agency": doc['agency'],
                        "publish_date": doc['publish_date'].isoformat() if doc['publish_date'] else None,
                        "effective_date": doc['effective_date'].isoformat() if doc['effective_date'] else None,
                        "status": doc['status']
                    },
                    "diagnostics": diagnostics
                })

            # Sort by final score
            scored_docs.sort(key=lambda x: x['score'], reverse=True)
            return scored_docs

        except Exception as e:
            logger.error(f"Final scoring error: {e}")
            return []

    def _calculate_final_score(self, doc: Dict, base_score: float, expanded_terms) -> float:
        """Calculate final document score with all factors."""
        score = 1.5 * base_score  # Base RRF score

        # Domain authority bonus
        domain_score = 0.7  # Default
        if "gov.cn" in doc.get('domain', '') or "nea.gov.cn" in doc.get('domain', ''):
            domain_score = 1.0
        score += 0.5 * domain_score

        # Freshness bonus (exponential decay over 6 years)
        effective_date = doc.get('effective_date') or doc.get('publish_date')
        if effective_date:
            age_years = (datetime.now().date() - effective_date.date()).days / 365.25
            freshness = math.exp(-age_years / 6.0)
            score += 1.2 * freshness

        # On-topic bonus (phrase matches)
        on_topic_score = 0.0
        search_terms = set(expanded_terms.get("provinces", []) +
                          expanded_terms.get("doc_classes", []) +
                          expanded_terms.get("assets", []))

        title = doc.get('title', '') or ''
        headings = doc.get('headings', '') or ''

        for term in search_terms:
            if term.lower() in title.lower():
                on_topic_score += 1.0
            if term.lower() in headings.lower():
                on_topic_score += 0.5

        score += 1.0 * min(on_topic_score, 3.0)  # Cap at 3.0

        # Wenhao bonus (exact document number match)
        if doc.get('wenhao') and any(term.lower() in doc['wenhao'].lower() for term in search_terms):
            score += 1.0

        return score

    def _build_diagnostics(self, doc: Dict, expanded_terms) -> Dict:
        """Build diagnostic information for transparency."""
        search_terms = set(expanded_terms.get("provinces", []) +
                          expanded_terms.get("doc_classes", []) +
                          expanded_terms.get("assets", []))

        why_matched = []

        # Check what matched
        if doc.get('title'):
            for term in search_terms:
                if term.lower() in doc['title'].lower():
                    why_matched.append(f"title_phrase:{term}")

        if doc.get('headings'):
            for term in search_terms:
                if term.lower() in doc['headings'].lower():
                    why_matched.append(f"headings_phrase:{term}")

        if doc.get('wenhao'):
            for term in search_terms:
                if term.lower() in doc['wenhao'].lower():
                    why_matched.append(f"wenhao_match:{term}")

        if doc.get('status'):
            why_matched.append(f"status:{doc['status']}")

        if doc.get('province_normalized'):
            why_matched.append(f"province:{doc['province_normalized']}")

        return {
            "matched_terms": list(search_terms),
            "why_matched": why_matched,
            "freshness_score": self._calculate_freshness(doc),
            "domain_authority": "high" if "gov.cn" in doc.get('domain', '') else "medium"
        }

    def _calculate_freshness(self, doc: Dict) -> float:
        """Calculate document freshness score."""
        effective_date = doc.get('effective_date') or doc.get('publish_date')
        if not effective_date:
            return 0.0

        age_years = (datetime.now().date() - effective_date.date()).days / 365.25
        return math.exp(-age_years / 6.0)

    def _apply_refusal_threshold(self, scored_docs: List[Dict]) -> Tuple[List[Dict], bool]:
        """Apply refusal threshold and return results."""
        if not scored_docs:
            return [], True

        # Get top document score
        top_score = scored_docs[0]['score']

        if top_score < self.refusal_threshold:
            return [], True

        # Return top results (limit to 5)
        return scored_docs[:5], False
