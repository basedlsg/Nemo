# Query normalization and expansion for Chinese energy regulations
# Implements deterministic constraints before ranking

from typing import Dict, Any

PROVINCE_SYNONYMS = {
    "guangdong": ["广东", "广东省", "粤", "guangdong", "gd"],
    "beijing": ["北京", "北京市", "京", "beijing", "bj"],
    "shanghai": ["上海", "上海市", "沪", "shanghai", "sh"],
    "shandong": ["山东", "山东省", "鲁", "shandong", "sd"],
    "inner_mongolia": ["内蒙古", "内蒙古自治区", "内蒙", "inner_mongolia", "nm"],
    "fujian": ["福建", "福建省", "闽", "fujian", "fj"],
    "sichuan": ["四川", "四川省", "蜀", "sichuan", "sc"],
    "guangxi": ["广西", "广西壮族自治区", "桂", "guangxi"],
    "hubei": ["湖北", "湖北省", "鄂", "hubei", "hb"],
    "hunan": ["湖南", "湖南省", "湘", "hunan", "hn"],
    "henan": ["河南", "河南省", "豫", "henan", "ha"],
    "hebei": ["河北", "河北省", "冀", "hebei", "he"],
    "shanxi": ["山西", "山西省", "晋", "shanxi", "sx"],
    "liaoning": ["辽宁", "辽宁省", "辽", "liaoning", "ln"],
    "jilin": ["吉林", "吉林省", "吉", "jilin", "jl"],
    "heilongjiang": ["黑龙江", "黑龙江省", "黑", "heilongjiang", "hlj"],
    "jiangsu": ["江苏", "江苏省", "苏", "jiangsu", "js"],
    "zhejiang": ["浙江", "浙江省", "浙", "zhejiang", "zj"],
    "anhui": ["安徽", "安徽省", "皖", "anhui", "ah"],
    "jiangxi": ["江西", "江西省", "赣", "jiangxi", "jx"],
    "shaanxi": ["陕西", "陕西省", "陕", "shaanxi", "sn"],
    "gansu": ["甘肃", "甘肃省", "甘", "gansu", "gs"],
    "qinghai": ["青海", "青海省", "青", "qinghai", "qh"],
    "ningxia": ["宁夏", "宁夏回族自治区", "宁", "ningxia", "nx"],
    "xinjiang": ["新疆", "新疆维吾尔自治区", "新", "xinjiang", "xj"],
    "yunnan": ["云南", "云南省", "云", "yunnan", "yn"],
    "guizhou": ["贵州", "贵州省", "贵", "guizhou", "gz"],
    "tibet": ["西藏", "西藏自治区", "藏", "tibet", "xz"],
    "hainan": ["海南", "海南省", "琼", "hainan"],
    "chongqing": ["重庆", "重庆市", "渝", "chongqing"],
    "tianjin": ["天津", "天津市", "津", "tianjin"],
    "neimenggu": ["内蒙古", "内蒙古自治区", "内蒙", "neimenggu", "nmg"]
}

DOC_CLASS_SYNONYMS = {
    "grid_connection": [
        "并网", "接网", "电网接入", "接入系统", "并网管理办法",
        "并网技术规定", "并网条件", "并网要求", "并网验收",
        "grid_connection", "grid_integration", "connection"
    ],
    "project_approval": [
        "核准", "备案", "可研", "批复", "审批", "开工许可",
        "项目审批", "项目核准", "项目备案", "前期手续",
        "project_approval", "project_clearance", "approval"
    ],
    "technical_standards": [
        "技术规范", "技术标准", "导则", "细则", "办法",
        "技术要求", "技术规定", "技术指南", "技术标准",
        "technical_standards", "technical_specs", "standards"
    ],
    "market_rules": [
        "市场规则", "交易规则", "电价", "补贴", "竞价",
        "市场准入", "交易机制", "价格机制", "辅助服务",
        "market_rules", "trading_rules", "market_regulation"
    ],
    "regulations": [
        "法规", "条例", "规定", "办法", "实施细则",
        "管理规定", "工作规程", "regulations", "rules"
    ],
    "environmental_protection": [
        "环保", "环境影响", "环评", "环境保护", "生态保护",
        "environmental_protection", "environment", "environmental"
    ],
    "dispatch_ops": [
        "调度", "调度规则", "调度技术", "运行", "调度操作",
        "dispatch", "operations", "grid_operations"
    ]
}

ASSET_SYNONYMS = {
    "solar": [
        "光伏", "光伏发电", "分布式光伏", "集中式光伏",
        "光伏电站", "太阳能", "solar", "photovoltaic", "pv"
    ],
    "wind": [
        "风电", "风力发电", "陆上风电", "海上风电",
        "风电站", "风能", "wind", "wind_power"
    ],
    "bess": [
        "储能", "电化学储能", "电池储能", "储能电站",
        "储能系统", "电能存储", "bess", "battery_storage"
    ],
    "renewable": [
        "可再生能源", "新能源", "清洁能源", "非化石能源",
        "renewable", "clean_energy", "new_energy"
    ],
    "coal_flex": [
        "煤电灵活性", "煤电机组灵活性", "深度调峰",
        "coal_flex", "coal_flexibility", "flexible_coal"
    ],
    "offshore_wind": [
        "海上风电", "离岸风电", "offshore_wind", "offshore"
    ],
    "hybrid_renewable": [
        "混合新能源", "多能互补", "hybrid_renewable", "hybrid"
    ]
}

def expand_terms(query):
    """
    Expand query terms using synonym mappings for better recall.
    Returns expanded terms for provinces, doc_classes, and assets.
    """
    from typing import Dict, List, Set

    # Get base terms
    base_province = query.province.lower() if query.province else ""
    base_doc_class = query.doc_class.lower() if query.doc_class else ""
    base_asset = query.asset.lower() if query.asset else ""

    # Expand provinces
    provinces = {base_province} if base_province else set()
    if base_province in PROVINCE_SYNONYMS:
        provinces.update(PROVINCE_SYNONYMS[base_province])

    # Expand doc classes
    doc_classes = {base_doc_class} if base_doc_class else set()
    if base_doc_class in DOC_CLASS_SYNONYMS:
        doc_classes.update(DOC_CLASS_SYNONYMS[base_doc_class])

    # Expand assets
    assets = set()
    if base_asset:
        assets.add(base_asset)
        if base_asset in ASSET_SYNONYMS:
            assets.update(ASSET_SYNONYMS[base_asset])

    return {
        "provinces": list(provinces),
        "doc_classes": list(doc_classes),
        "assets": list(assets)
    }

def get_hard_filters(query) -> Dict:
    """
    Generate hard filters that documents must satisfy.
    These are applied before ranking to ensure relevance.
    """
    expanded = expand_terms(query)

    filters = {
        "province_normalized": expanded["provinces"],
        "doc_class_normalized": expanded["doc_classes"],
        "status": ["现行有效"],  # Default to current valid documents
        "domain_in_allowlist": True
    }

    # Add asset filter if specified
    if expanded["assets"]:
        filters["asset_normalized"] = expanded["assets"]

    # Relax status filter if user asks about historical documents
    question_lower = query.question.lower()
    if any(term in question_lower for term in ["历史", "过去", "以前", "已废止", "失效", "historical", "old", "previous"]):
        filters["status"] = ["现行有效", "失效", "废止", "部分失效"]

    return filters

def normalize_province_name(province: str) -> str:
    """Normalize province name to standard format."""
    if not province:
        return ""

    province_lower = province.lower().strip()

    # Try to find in synonyms
    for standard, synonyms in PROVINCE_SYNONYMS.items():
        if province_lower in synonyms:
            return standard

    # Return as-is if no match found
    return province_lower

def normalize_doc_class(doc_class: str) -> str:
    """Normalize document class to standard format."""
    if not doc_class:
        return ""

    doc_class_lower = doc_class.lower().strip()

    # Try to find in synonyms
    for standard, synonyms in DOC_CLASS_SYNONYMS.items():
        if doc_class_lower in synonyms:
            return standard

    # Return as-is if no match found
    return doc_class_lower
