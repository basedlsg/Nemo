"""Knowledge base for Chinese energy regulation ontology."""

from typing import Dict, List, Set
from .schemas import (
    Jurisdiction, MarketCode, AssetType, Lifecycle, RequirementType, ParameterType,
    JurisdictionNode, MarketNode, AssetNode, LifecycleNode, RequirementNode, ParameterNode
)


class EnergyOntologyKB:
    """Knowledge base for Chinese energy regulation ontology."""
    
    def __init__(self):
        """Initialize knowledge base with predefined ontology."""
        self.jurisdictions = self._build_jurisdictions()
        self.markets = self._build_markets()
        self.assets = self._build_assets()
        self.lifecycles = self._build_lifecycles()
        self.requirements = self._build_requirements()
        self.parameters = self._build_parameters()
        
        # Build lookup indices
        self._build_keyword_indices()
    
    def _build_jurisdictions(self) -> Dict[Jurisdiction, JurisdictionNode]:
        """Build jurisdiction nodes."""
        return {
            Jurisdiction.GUANGDONG: JurisdictionNode(
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Guangdong Province",
                name_zh="广东省",
                description="Guangdong Province energy regulations",
                keywords=["guangdong", "gd", "pearl river delta"],
                keywords_zh=["广东", "粤", "珠三角", "广东省"],
                market_codes=[
                    MarketCode.GRID_CONNECTION,
                    MarketCode.MARKET_RULES,
                    MarketCode.DISPATCH_OPS,
                    MarketCode.RENEWABLE_POLICY
                ]
            ),
            
            Jurisdiction.SHANDONG: JurisdictionNode(
                jurisdiction=Jurisdiction.SHANDONG,
                name="Shandong Province", 
                name_zh="山东省",
                description="Shandong Province energy regulations",
                keywords=["shandong", "sd", "bohai bay"],
                keywords_zh=["山东", "鲁", "山东省", "渤海湾"],
                market_codes=[
                    MarketCode.GRID_CONNECTION,
                    MarketCode.DISPATCH_OPS,
                    MarketCode.RENEWABLE_POLICY,
                    MarketCode.COAL_FLEXIBILITY
                ]
            ),
            
            Jurisdiction.INNER_MONGOLIA: JurisdictionNode(
                jurisdiction=Jurisdiction.INNER_MONGOLIA,
                name="Inner Mongolia",
                name_zh="内蒙古自治区", 
                description="Inner Mongolia energy regulations",
                keywords=["inner mongolia", "mongolia", "im"],
                keywords_zh=["内蒙古", "蒙", "内蒙", "内蒙古自治区"],
                market_codes=[
                    MarketCode.GRID_CONNECTION,
                    MarketCode.RENEWABLE_POLICY,
                    MarketCode.COAL_FLEXIBILITY
                ]
            ),
            
            Jurisdiction.SICHUAN: JurisdictionNode(
                jurisdiction=Jurisdiction.SICHUAN,
                name="Sichuan Province",
                name_zh="四川省",
                description="Sichuan Province energy regulations (queued)",
                keywords=["sichuan", "sc", "chengdu"],
                keywords_zh=["四川", "川", "四川省", "成都"],
                market_codes=[
                    MarketCode.GRID_CONNECTION,
                    MarketCode.MARKET_RULES,
                    MarketCode.RENEWABLE_POLICY
                ]
            )
        }
    
    def _build_markets(self) -> Dict[MarketCode, MarketNode]:
        """Build market/regulation code nodes."""
        return {
            MarketCode.GRID_CONNECTION: MarketNode(
                market_code=MarketCode.GRID_CONNECTION,
                jurisdiction=Jurisdiction.GUANGDONG,  # Default, varies by context
                name="Grid Connection",
                name_zh="电网接入",
                description="Grid connection procedures and requirements",
                keywords=["grid connection", "interconnection", "grid access"],
                keywords_zh=["电网接入", "并网", "接入", "电网连接", "接入系统"],
                asset_types=[AssetType.WIND, AssetType.SOLAR, AssetType.BESS, AssetType.GENERAL]
            ),
            
            MarketCode.MARKET_RULES: MarketNode(
                market_code=MarketCode.MARKET_RULES,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Market Trading Rules",
                name_zh="市场交易规则",
                description="Electricity market trading rules and procedures",
                keywords=["market rules", "trading", "electricity market"],
                keywords_zh=["市场规则", "交易规则", "电力市场", "市场交易", "交易"],
                asset_types=[AssetType.GENERAL, AssetType.WIND, AssetType.SOLAR, AssetType.BESS]
            ),
            
            MarketCode.DISPATCH_OPS: MarketNode(
                market_code=MarketCode.DISPATCH_OPS,
                jurisdiction=Jurisdiction.SHANDONG,
                name="Dispatch Operations",
                name_zh="调度运行",
                description="Power system dispatch and operations",
                keywords=["dispatch", "operations", "system operations"],
                keywords_zh=["调度", "运行", "调度运行", "系统运行", "电力调度"],
                asset_types=[AssetType.GENERAL, AssetType.WIND, AssetType.SOLAR, AssetType.COAL]
            ),
            
            MarketCode.RENEWABLE_POLICY: MarketNode(
                market_code=MarketCode.RENEWABLE_POLICY,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Renewable Energy Policy",
                name_zh="可再生能源政策",
                description="Renewable energy policies and incentives",
                keywords=["renewable", "clean energy", "green energy"],
                keywords_zh=["可再生能源", "清洁能源", "绿色能源", "新能源", "可再生"],
                asset_types=[AssetType.WIND, AssetType.SOLAR, AssetType.HYDRO]
            ),
            
            MarketCode.STORAGE_POLICY: MarketNode(
                market_code=MarketCode.STORAGE_POLICY,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Energy Storage Policy",
                name_zh="储能政策",
                description="Energy storage policies and regulations",
                keywords=["storage", "battery", "energy storage"],
                keywords_zh=["储能", "电池", "储能系统", "蓄能", "储电"],
                asset_types=[AssetType.BESS]
            ),
            
            MarketCode.COAL_FLEXIBILITY: MarketNode(
                market_code=MarketCode.COAL_FLEXIBILITY,
                jurisdiction=Jurisdiction.INNER_MONGOLIA,
                name="Coal Flexibility",
                name_zh="煤电灵活性",
                description="Coal power flexibility and retrofits",
                keywords=["coal flexibility", "thermal flexibility"],
                keywords_zh=["煤电灵活性", "火电灵活性", "灵活性改造", "煤电", "火电"],
                asset_types=[AssetType.COAL]
            )
        }
    
    def _build_assets(self) -> Dict[AssetType, AssetNode]:
        """Build asset type nodes."""
        return {
            AssetType.WIND: AssetNode(
                asset_type=AssetType.WIND,
                market_code=MarketCode.RENEWABLE_POLICY,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Wind Power",
                name_zh="风力发电",
                description="Wind power generation assets",
                keywords=["wind", "wind power", "wind farm", "turbine"],
                keywords_zh=["风电", "风力发电", "风场", "风机", "风力", "风能"],
                lifecycles=[Lifecycle.PLANNING, Lifecycle.DEVELOPMENT, Lifecycle.CONSTRUCTION, 
                           Lifecycle.COMMISSIONING, Lifecycle.OPERATION, Lifecycle.MAINTENANCE]
            ),
            
            AssetType.SOLAR: AssetNode(
                asset_type=AssetType.SOLAR,
                market_code=MarketCode.RENEWABLE_POLICY,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Solar Power",
                name_zh="太阳能发电",
                description="Solar photovoltaic generation assets",
                keywords=["solar", "photovoltaic", "pv", "solar farm"],
                keywords_zh=["太阳能", "光伏", "太阳能发电", "光伏发电", "太阳能电站"],
                lifecycles=[Lifecycle.PLANNING, Lifecycle.DEVELOPMENT, Lifecycle.CONSTRUCTION,
                           Lifecycle.COMMISSIONING, Lifecycle.OPERATION, Lifecycle.MAINTENANCE]
            ),
            
            AssetType.BESS: AssetNode(
                asset_type=AssetType.BESS,
                market_code=MarketCode.STORAGE_POLICY,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Battery Energy Storage",
                name_zh="电池储能系统",
                description="Battery energy storage systems",
                keywords=["battery", "storage", "bess", "energy storage"],
                keywords_zh=["储能", "电池", "储能系统", "电池储能", "蓄电池"],
                lifecycles=[Lifecycle.PLANNING, Lifecycle.DEVELOPMENT, Lifecycle.CONSTRUCTION,
                           Lifecycle.COMMISSIONING, Lifecycle.OPERATION, Lifecycle.MAINTENANCE]
            ),
            
            AssetType.COAL: AssetNode(
                asset_type=AssetType.COAL,
                market_code=MarketCode.COAL_FLEXIBILITY,
                jurisdiction=Jurisdiction.INNER_MONGOLIA,
                name="Coal Power",
                name_zh="煤电",
                description="Coal-fired power generation",
                keywords=["coal", "thermal", "coal power", "fossil"],
                keywords_zh=["煤电", "火电", "燃煤", "煤炭", "火力发电"],
                lifecycles=[Lifecycle.OPERATION, Lifecycle.MAINTENANCE, Lifecycle.DECOMMISSIONING]
            ),
            
            AssetType.GENERAL: AssetNode(
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.MARKET_RULES,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="General/Multiple Assets",
                name_zh="通用/多种资产",
                description="Applies to multiple asset types",
                keywords=["general", "all", "multiple", "various"],
                keywords_zh=["通用", "所有", "各类", "多种", "一般"],
                lifecycles=[Lifecycle.GENERAL]
            )
        }
    
    def _build_lifecycles(self) -> Dict[Lifecycle, LifecycleNode]:
        """Build lifecycle stage nodes."""
        return {
            Lifecycle.PLANNING: LifecycleNode(
                lifecycle=Lifecycle.PLANNING,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.GRID_CONNECTION,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Planning Phase",
                name_zh="规划阶段",
                description="Project planning and feasibility",
                keywords=["planning", "feasibility", "development"],
                keywords_zh=["规划", "可行性", "前期", "筹备", "计划"],
                requirement_types=[RequirementType.PROCEDURAL, RequirementType.ENVIRONMENTAL, RequirementType.TECHNICAL]
            ),
            
            Lifecycle.DEVELOPMENT: LifecycleNode(
                lifecycle=Lifecycle.DEVELOPMENT,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.GRID_CONNECTION,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Development Phase",
                name_zh="开发阶段",
                description="Project development and permitting",
                keywords=["development", "permitting", "approval"],
                keywords_zh=["开发", "审批", "许可", "核准", "备案"],
                requirement_types=[RequirementType.PROCEDURAL, RequirementType.FINANCIAL, RequirementType.ENVIRONMENTAL]
            ),
            
            Lifecycle.CONSTRUCTION: LifecycleNode(
                lifecycle=Lifecycle.CONSTRUCTION,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.GRID_CONNECTION,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Construction Phase",
                name_zh="建设阶段",
                description="Project construction and installation",
                keywords=["construction", "installation", "building"],
                keywords_zh=["建设", "施工", "安装", "建造", "工程"],
                requirement_types=[RequirementType.TECHNICAL, RequirementType.SAFETY, RequirementType.ENVIRONMENTAL]
            ),
            
            Lifecycle.COMMISSIONING: LifecycleNode(
                lifecycle=Lifecycle.COMMISSIONING,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.GRID_CONNECTION,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Commissioning Phase",
                name_zh="调试阶段",
                description="System testing and commissioning",
                keywords=["commissioning", "testing", "startup"],
                keywords_zh=["调试", "试运行", "验收", "测试", "启动"],
                requirement_types=[RequirementType.TECHNICAL, RequirementType.SAFETY, RequirementType.COMPLIANCE]
            ),
            
            Lifecycle.OPERATION: LifecycleNode(
                lifecycle=Lifecycle.OPERATION,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.DISPATCH_OPS,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Operation Phase",
                name_zh="运行阶段",
                description="Normal operations and performance",
                keywords=["operation", "performance", "generation"],
                keywords_zh=["运行", "运营", "发电", "生产", "操作"],
                requirement_types=[RequirementType.TECHNICAL, RequirementType.REPORTING, RequirementType.COMPLIANCE]
            ),
            
            Lifecycle.MAINTENANCE: LifecycleNode(
                lifecycle=Lifecycle.MAINTENANCE,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.DISPATCH_OPS,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Maintenance Phase",
                name_zh="维护阶段",
                description="Maintenance and repairs",
                keywords=["maintenance", "repair", "service"],
                keywords_zh=["维护", "维修", "保养", "检修", "服务"],
                requirement_types=[RequirementType.TECHNICAL, RequirementType.SAFETY, RequirementType.REPORTING]
            )
        }
    
    def _build_requirements(self) -> Dict[RequirementType, RequirementNode]:
        """Build requirement type nodes."""
        return {
            RequirementType.TECHNICAL: RequirementNode(
                requirement_type=RequirementType.TECHNICAL,
                lifecycle=Lifecycle.GENERAL,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.GRID_CONNECTION,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Technical Requirements",
                name_zh="技术要求",
                description="Technical specifications and standards",
                keywords=["technical", "specification", "standard", "requirement"],
                keywords_zh=["技术", "技术要求", "规范", "标准", "参数"],
                parameter_types=[ParameterType.CAPACITY, ParameterType.VOLTAGE, ParameterType.FREQUENCY, ParameterType.EFFICIENCY]
            ),
            
            RequirementType.PROCEDURAL: RequirementNode(
                requirement_type=RequirementType.PROCEDURAL,
                lifecycle=Lifecycle.DEVELOPMENT,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.GRID_CONNECTION,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Procedural Requirements",
                name_zh="程序要求",
                description="Administrative procedures and processes",
                keywords=["procedure", "process", "administrative", "approval"],
                keywords_zh=["程序", "流程", "手续", "审批", "办理"],
                parameter_types=[ParameterType.TIMELINE, ParameterType.GENERAL]
            ),
            
            RequirementType.FINANCIAL: RequirementNode(
                requirement_type=RequirementType.FINANCIAL,
                lifecycle=Lifecycle.DEVELOPMENT,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.MARKET_RULES,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Financial Requirements",
                name_zh="财务要求",
                description="Financial and economic requirements",
                keywords=["financial", "economic", "cost", "payment"],
                keywords_zh=["财务", "经济", "费用", "成本", "资金"],
                parameter_types=[ParameterType.COST, ParameterType.PERCENTAGE, ParameterType.GENERAL]
            ),
            
            RequirementType.SAFETY: RequirementNode(
                requirement_type=RequirementType.SAFETY,
                lifecycle=Lifecycle.CONSTRUCTION,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.GRID_CONNECTION,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Safety Requirements",
                name_zh="安全要求",
                description="Safety and protection requirements",
                keywords=["safety", "protection", "security"],
                keywords_zh=["安全", "保护", "防护", "安全性", "安全要求"],
                parameter_types=[ParameterType.DISTANCE, ParameterType.TEMPERATURE, ParameterType.GENERAL]
            ),
            
            RequirementType.ENVIRONMENTAL: RequirementNode(
                requirement_type=RequirementType.ENVIRONMENTAL,
                lifecycle=Lifecycle.PLANNING,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.RENEWABLE_POLICY,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Environmental Requirements",
                name_zh="环境要求",
                description="Environmental protection requirements",
                keywords=["environmental", "environment", "ecological"],
                keywords_zh=["环境", "环保", "生态", "环境保护", "环境要求"],
                parameter_types=[ParameterType.PERCENTAGE, ParameterType.GENERAL]
            ),
            
            RequirementType.REPORTING: RequirementNode(
                requirement_type=RequirementType.REPORTING,
                lifecycle=Lifecycle.OPERATION,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.DISPATCH_OPS,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Reporting Requirements",
                name_zh="报告要求",
                description="Data reporting and information disclosure",
                keywords=["reporting", "data", "information", "disclosure"],
                keywords_zh=["报告", "数据", "信息", "披露", "上报"],
                parameter_types=[ParameterType.TIMELINE, ParameterType.PERCENTAGE, ParameterType.GENERAL]
            )
        }
    
    def _build_parameters(self) -> Dict[ParameterType, ParameterNode]:
        """Build parameter type nodes."""
        return {
            ParameterType.CAPACITY: ParameterNode(
                parameter_type=ParameterType.CAPACITY,
                requirement_type=RequirementType.TECHNICAL,
                lifecycle=Lifecycle.GENERAL,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.GRID_CONNECTION,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Capacity",
                name_zh="容量",
                description="Power capacity specifications",
                keywords=["capacity", "power", "mw", "kw"],
                keywords_zh=["容量", "功率", "装机", "兆瓦", "千瓦", "MW", "KW"],
                unit="MW",
                value_range="0.1-1000 MW"
            ),
            
            ParameterType.VOLTAGE: ParameterNode(
                parameter_type=ParameterType.VOLTAGE,
                requirement_type=RequirementType.TECHNICAL,
                lifecycle=Lifecycle.GENERAL,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.GRID_CONNECTION,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Voltage",
                name_zh="电压",
                description="Voltage level specifications",
                keywords=["voltage", "kv", "volt"],
                keywords_zh=["电压", "千伏", "伏特", "KV", "电压等级"],
                unit="kV",
                value_range="0.4-500 kV"
            ),
            
            ParameterType.FREQUENCY: ParameterNode(
                parameter_type=ParameterType.FREQUENCY,
                requirement_type=RequirementType.TECHNICAL,
                lifecycle=Lifecycle.OPERATION,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.DISPATCH_OPS,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Frequency",
                name_zh="频率",
                description="System frequency specifications",
                keywords=["frequency", "hz", "hertz"],
                keywords_zh=["频率", "赫兹", "Hz", "系统频率"],
                unit="Hz",
                value_range="49.5-50.5 Hz"
            ),
            
            ParameterType.EFFICIENCY: ParameterNode(
                parameter_type=ParameterType.EFFICIENCY,
                requirement_type=RequirementType.TECHNICAL,
                lifecycle=Lifecycle.OPERATION,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.RENEWABLE_POLICY,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Efficiency",
                name_zh="效率",
                description="Energy conversion efficiency",
                keywords=["efficiency", "performance", "conversion"],
                keywords_zh=["效率", "转换效率", "性能", "能效"],
                unit="%",
                value_range="80-95%"
            ),
            
            ParameterType.TIMELINE: ParameterNode(
                parameter_type=ParameterType.TIMELINE,
                requirement_type=RequirementType.PROCEDURAL,
                lifecycle=Lifecycle.DEVELOPMENT,
                asset_type=AssetType.GENERAL,
                market_code=MarketCode.GRID_CONNECTION,
                jurisdiction=Jurisdiction.GUANGDONG,
                name="Timeline",
                name_zh="时间",
                description="Time-related requirements",
                keywords=["timeline", "time", "duration", "deadline"],
                keywords_zh=["时间", "期限", "工期", "时限", "截止"],
                unit="days/months",
                value_range="1-365 days"
            )
        }
    
    def _build_keyword_indices(self):
        """Build keyword lookup indices for fast matching."""
        self.keyword_to_jurisdiction = {}
        self.keyword_to_market = {}
        self.keyword_to_asset = {}
        self.keyword_to_lifecycle = {}
        self.keyword_to_requirement = {}
        self.keyword_to_parameter = {}
        
        # Build jurisdiction index
        for jurisdiction, node in self.jurisdictions.items():
            for keyword in node.keywords + node.keywords_zh:
                self.keyword_to_jurisdiction[keyword.lower()] = jurisdiction
        
        # Build market index
        for market, node in self.markets.items():
            for keyword in node.keywords + node.keywords_zh:
                self.keyword_to_market[keyword.lower()] = market
        
        # Build asset index
        for asset, node in self.assets.items():
            for keyword in node.keywords + node.keywords_zh:
                self.keyword_to_asset[keyword.lower()] = asset
        
        # Build lifecycle index
        for lifecycle, node in self.lifecycles.items():
            for keyword in node.keywords + node.keywords_zh:
                self.keyword_to_lifecycle[keyword.lower()] = lifecycle
        
        # Build requirement index
        for requirement, node in self.requirements.items():
            for keyword in node.keywords + node.keywords_zh:
                self.keyword_to_requirement[keyword.lower()] = requirement
        
        # Build parameter index
        for parameter, node in self.parameters.items():
            for keyword in node.keywords + node.keywords_zh:
                self.keyword_to_parameter[keyword.lower()] = parameter
    
    def get_jurisdiction_by_keyword(self, keyword: str) -> Jurisdiction:
        """Get jurisdiction by keyword match."""
        return self.keyword_to_jurisdiction.get(keyword.lower())
    
    def get_market_by_keyword(self, keyword: str) -> MarketCode:
        """Get market code by keyword match."""
        return self.keyword_to_market.get(keyword.lower())
    
    def get_asset_by_keyword(self, keyword: str) -> AssetType:
        """Get asset type by keyword match."""
        return self.keyword_to_asset.get(keyword.lower())
    
    def get_lifecycle_by_keyword(self, keyword: str) -> Lifecycle:
        """Get lifecycle by keyword match."""
        return self.keyword_to_lifecycle.get(keyword.lower())
    
    def get_requirement_by_keyword(self, keyword: str) -> RequirementType:
        """Get requirement type by keyword match."""
        return self.keyword_to_requirement.get(keyword.lower())
    
    def get_parameter_by_keyword(self, keyword: str) -> ParameterType:
        """Get parameter type by keyword match."""
        return self.keyword_to_parameter.get(keyword.lower())
    
    def get_all_keywords(self) -> Set[str]:
        """Get all keywords in the knowledge base."""
        all_keywords = set()
        
        for node_dict in [
            self.jurisdictions, self.markets, self.assets,
            self.lifecycles, self.requirements, self.parameters
        ]:
            for node in node_dict.values():
                all_keywords.update(kw.lower() for kw in node.keywords + node.keywords_zh)
        
        return all_keywords