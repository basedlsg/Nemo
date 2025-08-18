"""Integration service for ontology mapping with OCR chunks."""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from .mapper import OntologyMapper
from .schemas import CitationMapping, OntologyMappingResult, Jurisdiction
from services.ocr.schemas import ChunkData, CitationRow

logger = logging.getLogger(__name__)


class OntologyIntegrationService:
    """Integrates ontology mapping with OCR text chunks."""
    
    def __init__(self, mapper: Optional[OntologyMapper] = None):
        """Initialize integration service."""
        self.mapper = mapper or OntologyMapper()
        logger.info("Initialized ontology integration service")
    
    def enrich_citation_with_ontology(
        self, 
        citation_row: CitationRow, 
        chunks: List[ChunkData],
        known_jurisdiction: Optional[Jurisdiction] = None
    ) -> CitationRow:
        """
        Enrich citation row with ontology mapping.
        
        Args:
            citation_row: Citation row to enrich
            chunks: Text chunks from OCR
            known_jurisdiction: Known jurisdiction if available
            
        Returns:
            Enriched citation row with ontology metadata
        """
        try:
            logger.info(f"Enriching citation {citation_row.citation_id} with ontology")
            
            # Combine chunk content for mapping
            combined_text = self._combine_chunk_content(chunks)
            
            # Determine jurisdiction
            jurisdiction = known_jurisdiction
            if not jurisdiction:
                try:
                    jurisdiction = Jurisdiction(citation_row.province)
                except ValueError:
                    jurisdiction = Jurisdiction.GUANGDONG  # Default
            
            # Map to ontology
            mapping_result = self.mapper.map_text_to_ontology(combined_text, jurisdiction)
            
            # Get best mapping
            best_mapping = mapping_result.get_best_mapping()
            
            if best_mapping:
                # Update citation row with ontology information
                citation_row = self._apply_mapping_to_citation(citation_row, best_mapping)
                
                # Add ontology metadata to chunks
                enriched_chunks = self._enrich_chunks_with_ontology(chunks, mapping_result)
                citation_row.chunk_ids = [chunk.chunk_id for chunk in enriched_chunks]
                
                logger.info(f"Citation enriched with ontology path: {best_mapping.get_ontology_path()}")
            else:
                logger.warning(f"No suitable ontology mapping found for citation {citation_row.citation_id}")
            
            return citation_row
            
        except Exception as e:
            logger.error(f"Error enriching citation with ontology: {e}")
            return citation_row
    
    def map_chunks_to_ontology(
        self, 
        chunks: List[ChunkData], 
        known_jurisdiction: Optional[Jurisdiction] = None
    ) -> List[Dict[str, Any]]:
        """
        Map individual chunks to ontology structure.
        
        Args:
            chunks: Text chunks to map
            known_jurisdiction: Known jurisdiction if available
            
        Returns:
            List of chunk mappings with ontology information
        """
        chunk_mappings = []
        
        for chunk in chunks:
            try:
                # Map chunk to ontology
                mapping_result = self.mapper.map_text_to_ontology(chunk.content, known_jurisdiction)
                
                # Create chunk mapping
                chunk_mapping = {
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "token_count": chunk.token_count,
                    "clause_type": chunk.clause_type,
                    "ontology_mappings": [
                        {
                            "path": mapping.get_ontology_path(),
                            "confidence": mapping.get_overall_confidence(),
                            "jurisdiction": mapping.jurisdiction.value,
                            "market_code": mapping.market_code.value,
                            "asset_type": mapping.asset_type.value,
                            "lifecycle": mapping.lifecycle.value,
                            "requirement_type": mapping.requirement_type.value,
                            "parameter_type": mapping.parameter_type.value if mapping.parameter_type else None
                        }
                        for mapping in mapping_result.mappings
                    ],
                    "best_mapping": None
                }
                
                # Add best mapping
                best_mapping = mapping_result.get_best_mapping()
                if best_mapping:
                    chunk_mapping["best_mapping"] = {
                        "path": best_mapping.get_ontology_path(),
                        "confidence": best_mapping.get_overall_confidence()
                    }
                
                chunk_mappings.append(chunk_mapping)
                
            except Exception as e:
                logger.error(f"Error mapping chunk {chunk.chunk_id} to ontology: {e}")
                # Add empty mapping for failed chunks
                chunk_mappings.append({
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "error": str(e),
                    "ontology_mappings": [],
                    "best_mapping": None
                })
        
        return chunk_mappings
    
    def analyze_document_ontology_coverage(
        self, 
        chunks: List[ChunkData], 
        known_jurisdiction: Optional[Jurisdiction] = None
    ) -> Dict[str, Any]:
        """
        Analyze ontology coverage across document chunks.
        
        Args:
            chunks: Document chunks to analyze
            known_jurisdiction: Known jurisdiction if available
            
        Returns:
            Analysis of ontology coverage
        """
        try:
            # Map all chunks
            chunk_mappings = self.map_chunks_to_ontology(chunks, known_jurisdiction)
            
            # Analyze coverage
            analysis = {
                "total_chunks": len(chunks),
                "mapped_chunks": 0,
                "unmapped_chunks": 0,
                "avg_confidence": 0.0,
                "coverage_by_category": {
                    "jurisdictions": set(),
                    "market_codes": set(),
                    "asset_types": set(),
                    "lifecycles": set(),
                    "requirement_types": set(),
                    "parameter_types": set()
                },
                "confidence_distribution": {
                    "high": 0,  # >= 0.7
                    "medium": 0,  # 0.4-0.7
                    "low": 0  # < 0.4
                },
                "chunk_details": chunk_mappings
            }
            
            total_confidence = 0.0
            mapped_count = 0
            
            for chunk_mapping in chunk_mappings:
                if chunk_mapping.get("best_mapping"):
                    mapped_count += 1
                    confidence = chunk_mapping["best_mapping"]["confidence"]
                    total_confidence += confidence
                    
                    # Update confidence distribution
                    if confidence >= 0.7:
                        analysis["confidence_distribution"]["high"] += 1
                    elif confidence >= 0.4:
                        analysis["confidence_distribution"]["medium"] += 1
                    else:
                        analysis["confidence_distribution"]["low"] += 1
                    
                    # Update coverage by category
                    for mapping in chunk_mapping["ontology_mappings"]:
                        analysis["coverage_by_category"]["jurisdictions"].add(mapping["jurisdiction"])
                        analysis["coverage_by_category"]["market_codes"].add(mapping["market_code"])
                        analysis["coverage_by_category"]["asset_types"].add(mapping["asset_type"])
                        analysis["coverage_by_category"]["lifecycles"].add(mapping["lifecycle"])
                        analysis["coverage_by_category"]["requirement_types"].add(mapping["requirement_type"])
                        if mapping["parameter_type"]:
                            analysis["coverage_by_category"]["parameter_types"].add(mapping["parameter_type"])
            
            analysis["mapped_chunks"] = mapped_count
            analysis["unmapped_chunks"] = len(chunks) - mapped_count
            analysis["avg_confidence"] = total_confidence / mapped_count if mapped_count > 0 else 0.0
            
            # Convert sets to lists for JSON serialization
            for category in analysis["coverage_by_category"]:
                analysis["coverage_by_category"][category] = list(analysis["coverage_by_category"][category])
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing document ontology coverage: {e}")
            return {
                "error": str(e),
                "total_chunks": len(chunks),
                "mapped_chunks": 0
            }
    
    def _combine_chunk_content(self, chunks: List[ChunkData]) -> str:
        """Combine chunk content for ontology mapping."""
        return "\n".join(chunk.content for chunk in chunks)
    
    def _apply_mapping_to_citation(self, citation_row: CitationRow, mapping: CitationMapping) -> CitationRow:
        """Apply ontology mapping to citation row."""
        # Update citation with ontology information
        citation_row.asset = mapping.asset_type.value
        
        # Note: We could extend CitationRow to include more ontology fields
        # For now, we use the asset field and could add metadata
        
        return citation_row
    
    def _enrich_chunks_with_ontology(
        self, 
        chunks: List[ChunkData], 
        mapping_result: OntologyMappingResult
    ) -> List[ChunkData]:
        """Enrich chunks with ontology information."""
        # For now, return chunks as-is
        # In a full implementation, we might add ontology metadata to each chunk
        return chunks
    
    def get_ontology_statistics(self) -> Dict[str, Any]:
        """Get statistics about the ontology knowledge base."""
        kb = self.mapper.kb
        
        return {
            "jurisdictions": len(kb.jurisdictions),
            "market_codes": len(kb.markets),
            "asset_types": len(kb.assets),
            "lifecycles": len(kb.lifecycles),
            "requirement_types": len(kb.requirements),
            "parameter_types": len(kb.parameters),
            "total_keywords": len(kb.get_all_keywords()),
            "supported_jurisdictions": [j.value for j in kb.jurisdictions.keys()],
            "supported_market_codes": [m.value for m in kb.markets.keys()],
            "supported_asset_types": [a.value for a in kb.assets.keys()]
        }


def create_enriched_citation_from_chunks(
    chunks: List[ChunkData],
    citation_id: UUID,
    province: str,
    doc_class: str,
    title: str,
    url: str,
    checksum: str,
    effective_date=None,
    integration_service: Optional[OntologyIntegrationService] = None
) -> CitationRow:
    """
    Create enriched citation row from chunks with ontology mapping.
    
    Args:
        chunks: Text chunks from OCR
        citation_id: Citation UUID
        province: Province code
        doc_class: Document class
        title: Document title
        url: Source URL
        checksum: Document checksum
        effective_date: Document effective date
        integration_service: Ontology integration service
        
    Returns:
        Enriched citation row
    """
    # Create base citation row
    combined_content = "\n".join(chunk.content for chunk in chunks)
    
    citation_row = CitationRow(
        citation_id=citation_id,
        province=province,
        doc_class=doc_class,
        asset=None,  # Will be set by ontology mapping
        title=title,
        url=url,
        effective_date=effective_date,
        checksum=checksum,
        content=combined_content,
        chunk_ids=[chunk.chunk_id for chunk in chunks]
    )
    
    # Enrich with ontology if service provided
    if integration_service:
        try:
            jurisdiction = Jurisdiction(province)
        except ValueError:
            jurisdiction = None
        
        citation_row = integration_service.enrich_citation_with_ontology(
            citation_row, chunks, jurisdiction
        )
    
    return citation_row