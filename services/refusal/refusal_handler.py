"""Refusal handling system with structured error codes and user-friendly responses."""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class RefusalCode(str, Enum):
    """Standardized refusal codes for different failure scenarios."""
    
    # Citation-related refusals
    NO_FIRST_PARTY_CITATION = "no_first_party_citation"
    STALE_CITATION = "stale_citation"
    INSUFFICIENT_CITATIONS = "insufficient_citations"
    CITATION_QUALITY_LOW = "citation_quality_low"
    
    # Scope and policy refusals
    PROVINCE_MISMATCH = "province_mismatch"
    ASSET_NOT_SUPPORTED = "asset_not_supported"
    DOC_CLASS_UNAVAILABLE = "doc_class_unavailable"
    CROSS_PROVINCE_LEAKAGE = "cross_province_leakage"
    
    # Language and content refusals
    LANGUAGE_POLICY_VIOLATION = "language_policy_violation"
    UNSAFE_CONTENT = "unsafe_content"
    PROMPT_INJECTION = "prompt_injection"
    
    # System and processing refusals
    RETRIEVAL_FAILED = "retrieval_failed"
    COMPOSITION_FAILED = "composition_failed"
    GUARDRAILS_FAILED = "guardrails_failed"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SYSTEM_OVERLOAD = "system_overload"
    
    # Data quality refusals
    QUERY_TOO_VAGUE = "query_too_vague"
    QUERY_TOO_COMPLEX = "query_too_complex"
    CONFLICTING_REQUIREMENTS = "conflicting_requirements"


@dataclass
class RefusalResponse:
    """Structured refusal response with error details and suggestions."""
    
    code: RefusalCode
    message_zh: str
    message_en: str
    suggestion_zh: str
    suggestion_en: str
    policy_info: Optional[Dict[str, Any]] = None
    debug_info: Optional[Dict[str, Any]] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


class RefusalHandler:
    """
    Comprehensive refusal handling system that provides structured error responses.
    
    Features:
    - Standardized refusal codes for different failure scenarios
    - Bilingual error messages (Chinese primary, English secondary)
    - User-friendly suggestions for resolution
    - Policy information for transparency
    - Debug information for troubleshooting
    - Refusal statistics and monitoring
    """
    
    def __init__(self):
        """Initialize refusal handler with predefined responses."""
        self.refusal_templates = self._initialize_refusal_templates()
        self.refusal_stats = {
            "total_refusals": 0,
            "refusal_by_code": {},
            "refusal_by_province": {},
            "refusal_by_doc_class": {},
            "refusal_by_asset": {}
        }
    
    def _initialize_refusal_templates(self) -> Dict[RefusalCode, Dict[str, str]]:
        """Initialize predefined refusal response templates."""
        return {
            # Citation-related refusals
            RefusalCode.NO_FIRST_PARTY_CITATION: {
                "message_zh": "抱歉，没有找到来自官方一手来源的相关资料。",
                "message_en": "Sorry, no official first-party sources found for your query.",
                "suggestion_zh": "请尝试使用更具体的关键词，或选择不同的省份和资产类型。如需最新信息，建议直接联系相关政府部门。",
                "suggestion_en": "Try using more specific keywords or select different province/asset types. For latest information, contact relevant government departments directly."
            },
            
            RefusalCode.STALE_CITATION: {
                "message_zh": "找到的相关资料可能已过时，无法确保信息的时效性。",
                "message_en": "Found sources may be outdated and cannot guarantee information currency.",
                "suggestion_zh": "建议查询最新的官方文件，或联系相关部门确认当前有效的政策规定。",
                "suggestion_en": "Please check latest official documents or contact relevant departments for current policy information."
            },
            
            RefusalCode.INSUFFICIENT_CITATIONS: {
                "message_zh": "找到的相关资料数量不足，无法提供完整准确的答案。",
                "message_en": "Insufficient relevant sources found to provide complete and accurate answer.",
                "suggestion_zh": "请尝试调整查询条件，使用更广泛的关键词，或分解为多个具体问题。",
                "suggestion_en": "Try adjusting query conditions, use broader keywords, or break down into multiple specific questions."
            },
            
            RefusalCode.CITATION_QUALITY_LOW: {
                "message_zh": "找到的资料质量不符合回答标准，无法确保信息的准确性。",
                "message_en": "Found sources do not meet quality standards for accurate information.",
                "suggestion_zh": "建议直接查阅官方网站或联系相关部门获取权威信息。",
                "suggestion_en": "Recommend checking official websites directly or contacting relevant departments for authoritative information."
            },
            
            # Scope and policy refusals
            RefusalCode.PROVINCE_MISMATCH: {
                "message_zh": "查询内容与指定省份的政策范围不匹配。",
                "message_en": "Query content does not match the specified province's policy scope.",
                "suggestion_zh": "请确认查询的省份是否正确，或调整查询内容以匹配该省份的相关政策。",
                "suggestion_en": "Please confirm the correct province for your query or adjust content to match relevant policies."
            },
            
            RefusalCode.ASSET_NOT_SUPPORTED: {
                "message_zh": "指定的资产类型在当前省份暂不支持或无相关政策。",
                "message_en": "Specified asset type is not supported or has no relevant policies in current province.",
                "suggestion_zh": "请选择该省份支持的其他资产类型，或查询其他省份的相关政策。",
                "suggestion_en": "Please select other supported asset types for this province or check policies in other provinces."
            },
            
            RefusalCode.DOC_CLASS_UNAVAILABLE: {
                "message_zh": "指定的文档类别在当前条件下暂无可用资料。",
                "message_en": "Specified document class has no available materials under current conditions.",
                "suggestion_zh": "请尝试其他文档类别，或调整省份和资产类型的组合。",
                "suggestion_en": "Try other document classes or adjust province and asset type combinations."
            },
            
            RefusalCode.CROSS_PROVINCE_LEAKAGE: {
                "message_zh": "检测到跨省份信息泄露风险，为确保信息准确性已拒绝回答。",
                "message_en": "Cross-province information leakage risk detected, refused to ensure information accuracy.",
                "suggestion_zh": "请确保查询内容与指定省份一致，避免混合不同省份的政策信息。",
                "suggestion_en": "Ensure query content matches specified province and avoid mixing policies from different provinces."
            },
            
            # Language and content refusals
            RefusalCode.LANGUAGE_POLICY_VIOLATION: {
                "message_zh": "查询不符合中文优先的语言政策要求。",
                "message_en": "Query does not comply with Chinese-first language policy requirements.",
                "suggestion_zh": "请使用中文提交查询，系统将优先提供中文回答。如需英文摘要，请在查询中明确说明。",
                "suggestion_en": "Please submit queries in Chinese. The system provides Chinese responses by default. Request English summary explicitly if needed."
            },
            
            RefusalCode.UNSAFE_CONTENT: {
                "message_zh": "检测到查询内容可能包含不安全或不当信息。",
                "message_en": "Query content detected to potentially contain unsafe or inappropriate information.",
                "suggestion_zh": "请重新组织查询内容，确保符合政策规范和安全要求。",
                "suggestion_en": "Please reorganize query content to comply with policy standards and safety requirements."
            },
            
            RefusalCode.PROMPT_INJECTION: {
                "message_zh": "检测到可能的提示注入攻击，已拒绝处理该查询。",
                "message_en": "Potential prompt injection attack detected, query processing refused.",
                "suggestion_zh": "请使用正常的查询语言，避免包含系统指令或特殊格式。",
                "suggestion_en": "Please use normal query language and avoid including system instructions or special formats."
            },
            
            # System and processing refusals
            RefusalCode.RETRIEVAL_FAILED: {
                "message_zh": "检索系统暂时无法处理您的查询。",
                "message_en": "Retrieval system temporarily unable to process your query.",
                "suggestion_zh": "请稍后重试，或联系技术支持获取帮助。",
                "suggestion_en": "Please try again later or contact technical support for assistance."
            },
            
            RefusalCode.COMPOSITION_FAILED: {
                "message_zh": "答案生成系统暂时无法完成回答。",
                "message_en": "Answer composition system temporarily unable to complete response.",
                "suggestion_zh": "请尝试简化查询内容，或稍后重试。",
                "suggestion_en": "Try simplifying query content or retry later."
            },
            
            RefusalCode.GUARDRAILS_FAILED: {
                "message_zh": "安全检查系统检测到潜在风险，已拒绝处理。",
                "message_en": "Safety check system detected potential risks and refused processing.",
                "suggestion_zh": "请检查查询内容是否符合使用规范，或联系管理员获取帮助。",
                "suggestion_en": "Please check if query content complies with usage guidelines or contact administrator for help."
            },
            
            RefusalCode.RATE_LIMIT_EXCEEDED: {
                "message_zh": "查询频率超过限制，请稍后再试。",
                "message_en": "Query rate limit exceeded, please try again later.",
                "suggestion_zh": "请等待一段时间后重新提交查询，或联系管理员申请更高的访问限额。",
                "suggestion_en": "Wait for some time before resubmitting query or contact administrator for higher access limits."
            },
            
            RefusalCode.SYSTEM_OVERLOAD: {
                "message_zh": "系统当前负载过高，暂时无法处理新的查询。",
                "message_en": "System currently overloaded and temporarily unable to process new queries.",
                "suggestion_zh": "请稍后重试，或在系统负载较低的时间段提交查询。",
                "suggestion_en": "Please retry later or submit queries during lower system load periods."
            },
            
            # Data quality refusals
            RefusalCode.QUERY_TOO_VAGUE: {
                "message_zh": "查询内容过于模糊，无法提供准确的答案。",
                "message_en": "Query content too vague to provide accurate answer.",
                "suggestion_zh": "请提供更具体的查询内容，包括明确的省份、资产类型和具体问题。",
                "suggestion_en": "Please provide more specific query content including clear province, asset type, and specific questions."
            },
            
            RefusalCode.QUERY_TOO_COMPLEX: {
                "message_zh": "查询内容过于复杂，建议分解为多个简单问题。",
                "message_en": "Query content too complex, recommend breaking down into multiple simple questions.",
                "suggestion_zh": "请将复杂查询分解为多个具体的子问题，逐一提交查询。",
                "suggestion_en": "Break down complex query into multiple specific sub-questions and submit them individually."
            },
            
            RefusalCode.CONFLICTING_REQUIREMENTS: {
                "message_zh": "查询中包含相互冲突的要求，无法同时满足。",
                "message_en": "Query contains conflicting requirements that cannot be satisfied simultaneously.",
                "suggestion_zh": "请明确查询的优先级，或分别提交不同的查询以获取相应信息。",
                "suggestion_en": "Please clarify query priorities or submit separate queries to get corresponding information."
            }
        }
    
    def create_refusal(
        self,
        code: RefusalCode,
        context: Optional[Dict[str, Any]] = None,
        custom_message: Optional[str] = None,
        debug_info: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ) -> RefusalResponse:
        """
        Create a structured refusal response.
        
        Args:
            code: Refusal code indicating the type of failure
            context: Query context for personalized messages
            custom_message: Optional custom message to override template
            debug_info: Optional debug information for troubleshooting
            trace_id: Optional trace ID for request tracking
            
        Returns:
            Structured refusal response with bilingual messages and suggestions
        """
        try:
            # Get template for refusal code
            template = self.refusal_templates.get(code)
            if not template:
                logger.warning(f"No template found for refusal code: {code}")
                template = self._get_default_template()
            
            # Create base refusal response
            refusal = RefusalResponse(
                code=code,
                message_zh=custom_message or template["message_zh"],
                message_en=template["message_en"],
                suggestion_zh=template["suggestion_zh"],
                suggestion_en=template["suggestion_en"],
                debug_info=debug_info
            )
            
            # Add policy information if available
            if context:
                refusal.policy_info = self._generate_policy_info(code, context)
                
                # Personalize messages based on context
                refusal = self._personalize_refusal(refusal, context)
            
            # Update statistics
            self._update_refusal_stats(code, context, trace_id)
            
            logger.info(f"[{trace_id}] Created refusal response: {code.value}")
            
            return refusal
            
        except Exception as e:
            logger.error(f"Failed to create refusal response: {e}")
            return self._create_fallback_refusal(trace_id)
    
    def _get_default_template(self) -> Dict[str, str]:
        """Get default template for unknown refusal codes."""
        return {
            "message_zh": "抱歉，系统暂时无法处理您的查询。",
            "message_en": "Sorry, system temporarily unable to process your query.",
            "suggestion_zh": "请稍后重试，或联系技术支持获取帮助。",
            "suggestion_en": "Please try again later or contact technical support for assistance."
        }
    
    def _generate_policy_info(self, code: RefusalCode, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate policy information based on refusal code and context."""
        policy_info = {
            "refusal_code": code.value,
            "policy_category": self._get_policy_category(code),
            "applicable_scope": self._get_applicable_scope(context)
        }
        
        # Add specific policy details based on refusal code
        if code in [RefusalCode.NO_FIRST_PARTY_CITATION, RefusalCode.STALE_CITATION]:
            policy_info["citation_policy"] = {
                "requires_first_party": True,
                "max_age_days": 365,
                "min_citations": 1
            }
        
        elif code in [RefusalCode.PROVINCE_MISMATCH, RefusalCode.CROSS_PROVINCE_LEAKAGE]:
            policy_info["geo_policy"] = {
                "strict_province_matching": True,
                "cross_province_allowed": False,
                "supported_provinces": ["guangdong", "shandong", "inner_mongolia"]
            }
        
        elif code == RefusalCode.LANGUAGE_POLICY_VIOLATION:
            policy_info["language_policy"] = {
                "primary_language": "zh-CN",
                "english_summary_allowed": True,
                "requires_explicit_request": True
            }
        
        return policy_info
    
    def _get_policy_category(self, code: RefusalCode) -> str:
        """Get policy category for refusal code."""
        if code in [RefusalCode.NO_FIRST_PARTY_CITATION, RefusalCode.STALE_CITATION, RefusalCode.INSUFFICIENT_CITATIONS]:
            return "citation_quality"
        elif code in [RefusalCode.PROVINCE_MISMATCH, RefusalCode.CROSS_PROVINCE_LEAKAGE]:
            return "geographic_scope"
        elif code in [RefusalCode.LANGUAGE_POLICY_VIOLATION, RefusalCode.UNSAFE_CONTENT]:
            return "content_policy"
        elif code in [RefusalCode.RETRIEVAL_FAILED, RefusalCode.COMPOSITION_FAILED]:
            return "system_error"
        else:
            return "general"
    
    def _get_applicable_scope(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get applicable scope information from context."""
        return {
            "province": context.get("province"),
            "doc_class": context.get("doc_class"),
            "asset": context.get("asset"),
            "language": context.get("lang", "zh-CN")
        }
    
    def _personalize_refusal(self, refusal: RefusalResponse, context: Dict[str, Any]) -> RefusalResponse:
        """Personalize refusal messages based on query context."""
        province = context.get("province")
        asset = context.get("asset")
        doc_class = context.get("doc_class")
        
        # Province labels for personalization
        province_labels = {
            "guangdong": "广东省",
            "shandong": "山东省",
            "inner_mongolia": "内蒙古自治区"
        }
        
        asset_labels = {
            "wind": "风电",
            "solar": "光伏",
            "bess": "储能",
            "coal_flex": "煤电"
        }
        
        doc_class_labels = {
            "market_rules": "市场规则",
            "grid_connection": "并网规定",
            "dispatch_ops": "调度运行"
        }
        
        # Personalize messages with context
        if province and province in province_labels:
            province_label = province_labels[province]
            
            # Add province-specific suggestions
            if refusal.code == RefusalCode.NO_FIRST_PARTY_CITATION:
                refusal.suggestion_zh += f" 您也可以直接访问{province_label}电力交易中心官网获取最新信息。"
            
            elif refusal.code == RefusalCode.ASSET_NOT_SUPPORTED and asset:
                asset_label = asset_labels.get(asset, asset)
                refusal.message_zh = f"抱歉，{province_label}暂无{asset_label}相关的政策资料。"
        
        return refusal
    
    def _create_fallback_refusal(self, trace_id: Optional[str] = None) -> RefusalResponse:
        """Create fallback refusal response when normal processing fails."""
        return RefusalResponse(
            code=RefusalCode.SYSTEM_OVERLOAD,
            message_zh="系统出现异常，暂时无法处理您的查询。",
            message_en="System error occurred, temporarily unable to process your query.",
            suggestion_zh="请稍后重试，或联系技术支持。",
            suggestion_en="Please try again later or contact technical support.",
            debug_info={"fallback": True, "trace_id": trace_id}
        )
    
    def _update_refusal_stats(
        self,
        code: RefusalCode,
        context: Optional[Dict[str, Any]],
        trace_id: Optional[str]
    ):
        """Update refusal statistics."""
        try:
            self.refusal_stats["total_refusals"] += 1
            
            # Update refusal by code
            code_str = code.value
            self.refusal_stats["refusal_by_code"][code_str] = self.refusal_stats["refusal_by_code"].get(code_str, 0) + 1
            
            if context:
                # Update refusal by province
                province = context.get("province")
                if province:
                    self.refusal_stats["refusal_by_province"][province] = self.refusal_stats["refusal_by_province"].get(province, 0) + 1
                
                # Update refusal by doc_class
                doc_class = context.get("doc_class")
                if doc_class:
                    self.refusal_stats["refusal_by_doc_class"][doc_class] = self.refusal_stats["refusal_by_doc_class"].get(doc_class, 0) + 1
                
                # Update refusal by asset
                asset = context.get("asset")
                if asset:
                    self.refusal_stats["refusal_by_asset"][asset] = self.refusal_stats["refusal_by_asset"].get(asset, 0) + 1
        
        except Exception as e:
            logger.error(f"Failed to update refusal stats: {e}")
    
    def get_refusal_stats(self) -> Dict[str, Any]:
        """Get current refusal statistics."""
        return {
            **self.refusal_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_refusal_rate(self, total_queries: int) -> float:
        """Calculate refusal rate based on total queries."""
        if total_queries == 0:
            return 0.0
        return self.refusal_stats["total_refusals"] / total_queries
    
    def get_top_refusal_codes(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top refusal codes by frequency."""
        refusal_by_code = self.refusal_stats["refusal_by_code"]
        
        sorted_codes = sorted(
            refusal_by_code.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            {"code": code, "count": count, "percentage": count / max(self.refusal_stats["total_refusals"], 1)}
            for code, count in sorted_codes[:limit]
        ]
    
    def health_check(self) -> Dict[str, Any]:
        """Check refusal handler health."""
        try:
            return {
                "status": "healthy",
                "templates_loaded": len(self.refusal_templates),
                "total_refusals": self.refusal_stats["total_refusals"],
                "unique_codes": len(self.refusal_stats["refusal_by_code"]),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global refusal handler instance
_refusal_handler: Optional[RefusalHandler] = None


def get_refusal_handler() -> RefusalHandler:
    """Get global refusal handler instance."""
    global _refusal_handler
    if _refusal_handler is None:
        _refusal_handler = RefusalHandler()
    return _refusal_handler


def create_refusal(
    code: RefusalCode,
    context: Optional[Dict[str, Any]] = None,
    custom_message: Optional[str] = None,
    trace_id: Optional[str] = None
) -> RefusalResponse:
    """
    Convenience function for creating refusal responses.
    
    Args:
        code: Refusal code indicating the type of failure
        context: Query context for personalized messages
        custom_message: Optional custom message to override template
        trace_id: Optional trace ID for request tracking
        
    Returns:
        Structured refusal response
    """
    handler = get_refusal_handler()
    return handler.create_refusal(
        code=code,
        context=context,
        custom_message=custom_message,
        trace_id=trace_id
    )


if __name__ == "__main__":
    # Quick test of refusal handler
    def test_refusal_handler():
        print("=== Refusal Handler Test ===")
        
        handler = RefusalHandler()
        
        # Test health check
        print("\n--- Health Check ---")
        health = handler.health_check()
        print(f"Status: {health['status']}")
        print(f"Templates loaded: {health['templates_loaded']}")
        
        # Test refusal creation
        print("\n--- Refusal Creation Test ---")
        
        context = {
            "province": "guangdong",
            "doc_class": "grid_connection",
            "asset": "solar",
            "lang": "zh-CN"
        }
        
        refusal = handler.create_refusal(
            code=RefusalCode.NO_FIRST_PARTY_CITATION,
            context=context,
            trace_id="test-refusal-1"
        )
        
        print(f"Code: {refusal.code}")
        print(f"Message (ZH): {refusal.message_zh}")
        print(f"Message (EN): {refusal.message_en}")
        print(f"Suggestion (ZH): {refusal.suggestion_zh}")
        print(f"Policy info: {refusal.policy_info}")
        
        # Test statistics
        print("\n--- Statistics Test ---")
        stats = handler.get_refusal_stats()
        print(f"Total refusals: {stats['total_refusals']}")
        print(f"Refusal by code: {stats['refusal_by_code']}")
        
        top_codes = handler.get_top_refusal_codes(3)
        print(f"Top refusal codes: {top_codes}")
    
    test_refusal_handler()