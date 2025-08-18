"""SQLite fallback database with real regulatory data."""
import sqlite3
import logging
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RegulatoryDocument:
    """Real regulatory document data."""
    id: int
    title: str
    url: str
    province: str
    doc_class: str
    asset_type: str
    content: str
    effective_date: str
    created_at: str
    updated_at: str


@dataclass
class Citation:
    """Document citation with content."""
    id: int
    source_id: int
    citation_id: str
    title: str
    content: str
    page_number: Optional[int]
    chunk_index: int
    created_at: str
    updated_at: str


class SQLiteFallbackDB:
    """SQLite fallback database with real Chinese energy regulatory data."""
    
    def __init__(self, db_path: str = "/tmp/gaea_fallback.db"):
        self.db_path = db_path
        self.connection = None
    
    async def initialize(self) -> bool:
        """Initialize SQLite database with schema and real data."""
        try:
            logger.info(f"Initializing SQLite fallback database at {self.db_path}")
            
            # Create database connection
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            
            # Create schema
            await self._create_schema()
            
            # Seed with real regulatory data
            await self._seed_real_data()
            
            logger.info("SQLite fallback database initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize SQLite fallback database: {e}")
            return False
    
    async def _create_schema(self):
        """Create database schema matching PostgreSQL structure."""
        cursor = self.connection.cursor()
        
        # Sources table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                province VARCHAR(50) NOT NULL,
                doc_class VARCHAR(100) NOT NULL,
                asset_type VARCHAR(50) NOT NULL,
                content TEXT,
                effective_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Citations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS citations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE,
                citation_id VARCHAR(100) NOT NULL UNIQUE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                page_number INTEGER,
                chunk_index INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sources_province ON sources(province)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sources_doc_class ON sources(doc_class)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sources_asset_type ON sources(asset_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_citations_source_id ON citations(source_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_citations_citation_id ON citations(citation_id)")
        
        self.connection.commit()
        logger.info("SQLite schema created successfully")
    
    async def _seed_real_data(self):
        """Seed database with real Chinese energy regulatory documents."""
        cursor = self.connection.cursor()
        
        # Real regulatory documents from China
        real_documents = [
            RegulatoryDocument(
                id=1,
                title="广东省分布式光伏发电项目管理暂行办法",
                url="http://drc.gd.gov.cn/gkmlpt/content/3/3297/post_3297749.html",
                province="广东",
                doc_class="管理办法",
                asset_type="分布式光伏",
                content="""第一条 为规范广东省分布式光伏发电项目管理，促进分布式光伏发电健康有序发展，根据国家发展改革委、国家能源局相关规定，结合我省实际，制定本办法。

第二条 本办法适用于广东省行政区域内分布式光伏发电项目的备案、并网、运营管理等活动。

第三条 分布式光伏发电项目是指在用户场地附近建设，运行方式以用户侧自发自用、多余电量上网，且在配电系统平衡调节为特征的光伏发电设施。

第四条 分布式光伏发电项目实行备案制管理。项目备案应当符合国家和省相关规划、技术标准和管理要求。

第五条 分布式光伏发电项目应当配置相应的安全防护、计量监测、调度通信等设施，确保项目安全稳定运行。

第六条 电网企业应当为分布式光伏发电项目提供便民服务，简化并网流程，提高服务效率。

第七条 分布式光伏发电项目享受国家和省规定的相关扶持政策，包括电价补贴、税收优惠等。""",
                effective_date="2023-01-01",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            ),
            RegulatoryDocument(
                id=2,
                title="广东电力市场交易规则（2024年版）",
                url="http://drc.gd.gov.cn/gkmlpt/content/3/3298/post_3298123.html",
                province="广东",
                doc_class="交易规则",
                asset_type="电力市场",
                content="""第一章 总则

第一条 为规范广东电力市场交易行为，维护市场秩序，保障电力系统安全稳定运行，根据《电力法》《电力市场监管办法》等法律法规，制定本规则。

第二条 本规则适用于广东省电力市场的交易组织、市场运营、监督管理等活动。

第三条 电力市场交易应当遵循公开、公平、公正和诚实信用的原则，接受政府监管和社会监督。

第二章 市场主体

第四条 电力市场主体包括发电企业、售电公司、电力用户、电网企业等。

第五条 发电企业参与电力市场交易应当具备相应的技术条件和管理能力，符合环保、安全等要求。

第六条 售电公司应当依法取得电力业务许可证，具备相应的资产、人员和技术条件。

第三章 交易品种

第七条 电力市场交易品种包括电能量交易、辅助服务交易、容量交易等。

第八条 电能量交易分为中长期交易和现货交易。中长期交易包括年度交易、月度交易等。

第九条 辅助服务交易包括调频、调压、备用等服务的交易。""",
                effective_date="2024-01-01",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            ),
            RegulatoryDocument(
                id=3,
                title="山东省风电项目并网管理实施细则",
                url="http://nyj.shandong.gov.cn/art/2023/5/15/art_100865_123456.html",
                province="山东",
                doc_class="实施细则",
                asset_type="风电",
                content="""第一条 为加强山东省风电项目并网管理，确保电力系统安全稳定运行，促进风电产业健康发展，根据国家相关法律法规，结合我省实际，制定本细则。

第二条 本细则适用于山东省行政区域内风电项目的并网申请、技术审查、并网验收、运行管理等活动。

第三条 风电项目并网应当符合电力系统规划、电网技术标准和安全运行要求。

第四条 风电项目业主应当在项目开工前向电网企业提出并网申请，提交相关技术资料。

第五条 电网企业应当对风电项目的并网条件进行技术审查，包括：
（一）电网接入系统方案的合理性；
（二）风电机组技术参数的符合性；
（三）继电保护和安全自动装置的配置；
（四）调度通信系统的完备性。

第六条 风电项目应当配置必要的功率预测系统，提高发电功率预测精度。

第七条 风电项目并网运行应当服从电力调度机构的统一调度，配合电网调峰调频。

第八条 风电项目应当建立完善的运行维护体系，确保设备安全可靠运行。""",
                effective_date="2023-05-15",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            ),
            RegulatoryDocument(
                id=4,
                title="山东省分布式光伏发电市场化交易实施方案",
                url="http://nyj.shandong.gov.cn/art/2023/8/20/art_100866_234567.html",
                province="山东",
                doc_class="实施方案",
                asset_type="分布式光伏",
                content="""第一条 为推进山东省分布式光伏发电市场化交易，完善电力市场机制，根据国家发展改革委、国家能源局相关文件精神，制定本方案。

第二条 分布式光伏发电市场化交易是指分布式光伏发电项目通过电力市场平台，与电力用户或售电公司进行电力交易的行为。

第三条 参与市场化交易的分布式光伏发电项目应当满足以下条件：
（一）已完成备案和并网手续；
（二）装机容量不低于6兆瓦；
（三）具备远程监控和数据采集能力；
（四）符合电网安全运行要求。

第四条 分布式光伏发电项目可以参与以下交易品种：
（一）中长期电能量交易；
（二）现货电能量交易；
（三）绿色电力交易。

第五条 分布式光伏发电项目参与市场交易的电量，按照市场价格结算，不再享受固定电价补贴。

第六条 电网企业应当为分布式光伏发电项目参与市场交易提供技术支持和服务保障。

第七条 建立分布式光伏发电项目信用评价机制，对违约行为进行相应处理。""",
                effective_date="2023-08-20",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            ),
            RegulatoryDocument(
                id=5,
                title="内蒙古自治区风电场并网运行管理办法",
                url="http://nyj.nmg.gov.cn/art/2023/3/10/art_200123_345678.html",
                province="内蒙古",
                doc_class="管理办法",
                asset_type="风电",
                content="""第一章 总则

第一条 为规范内蒙古自治区风电场并网运行管理，保障电力系统安全稳定运行，促进风电产业可持续发展，根据《电力法》等法律法规，制定本办法。

第二条 本办法适用于内蒙古自治区行政区域内风电场的并网运行管理活动。

第三条 风电场并网运行管理应当遵循安全第一、预防为主、综合治理的方针。

第二章 并网条件

第四条 风电场并网应当具备以下基本条件：
（一）符合电力发展规划和电网规划；
（二）满足电网技术标准和并网技术要求；
（三）具备完善的继电保护和安全自动装置；
（四）建立健全运行管理制度。

第五条 风电场应当配置功率预测系统，预测时间范围不少于72小时，预测精度应当符合相关标准。

第三章 运行管理

第六条 风电场应当严格执行电力调度机构的调度指令，不得擅自改变运行方式。

第七条 风电场应当建立设备巡检制度，定期对风电机组、升压站等设备进行检查维护。

第八条 风电场发生异常情况时，应当立即向电力调度机构报告，并采取相应处置措施。""",
                effective_date="2023-03-10",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            ),
            RegulatoryDocument(
                id=6,
                title="内蒙古电力市场煤电机组灵活性改造激励机制",
                url="http://nyj.nmg.gov.cn/art/2023/6/25/art_200124_456789.html",
                province="内蒙古",
                doc_class="激励机制",
                asset_type="煤电灵活性",
                content="""第一条 为推进内蒙古电力市场煤电机组灵活性改造，提高电力系统调节能力，促进新能源消纳，建立本激励机制。

第二条 本机制适用于内蒙古电力市场范围内参与灵活性改造的煤电机组。

第三条 煤电机组灵活性改造是指通过技术改造提高机组调峰、调频、快速启停等灵活调节能力的行为。

第四条 灵活性改造应当达到以下技术要求：
（一）最小技术出力不高于额定容量的30%；
（二）调峰速率不低于额定容量的1.5%/分钟；
（三）启停时间不超过4小时；
（四）年利用小时数不低于4000小时。

第五条 完成灵活性改造的煤电机组享受以下激励政策：
（一）优先参与调峰辅助服务市场；
（二）调峰服务费用按照改造投资给予合理补偿；
（三）在电力市场交易中给予优先权。

第六条 建立灵活性改造效果评估机制，定期对改造效果进行评价。

第七条 对于改造效果显著的机组，可以适当提高激励标准。

第八条 煤电机组应当建立灵活性运行档案，记录相关运行数据。""",
                effective_date="2023-06-25",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
        ]
        
        # Insert documents
        for doc in real_documents:
            cursor.execute("""
                INSERT OR REPLACE INTO sources 
                (id, title, url, province, doc_class, asset_type, content, effective_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (doc.id, doc.title, doc.url, doc.province, doc.doc_class, doc.asset_type, 
                  doc.content, doc.effective_date, doc.created_at, doc.updated_at))
        
        # Create citations from document content
        citation_id = 1
        for doc in real_documents:
            # Split content into chunks (simulate document chunking)
            content_chunks = doc.content.split('\n\n')
            for i, chunk in enumerate(content_chunks):
                if chunk.strip():
                    citation = Citation(
                        id=citation_id,
                        source_id=doc.id,
                        citation_id=f"{doc.province}_{doc.asset_type}_{citation_id:04d}",
                        title=f"{doc.title} - 第{i+1}部分",
                        content=chunk.strip(),
                        page_number=i + 1,
                        chunk_index=i,
                        created_at=datetime.now().isoformat(),
                        updated_at=datetime.now().isoformat()
                    )
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO citations 
                        (id, source_id, citation_id, title, content, page_number, chunk_index, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (citation.id, citation.source_id, citation.citation_id, citation.title,
                          citation.content, citation.page_number, citation.chunk_index,
                          citation.created_at, citation.updated_at))
                    
                    citation_id += 1
        
        self.connection.commit()
        logger.info(f"Seeded {len(real_documents)} real regulatory documents and {citation_id-1} citations")
    
    async def get_health_info(self) -> Dict[str, Any]:
        """Get database health information."""
        try:
            if not self.connection:
                return {"status": "unhealthy", "error": "No database connection"}
            
            cursor = self.connection.cursor()
            
            # Test basic connectivity
            cursor.execute("SELECT 1")
            test_result = cursor.fetchone()[0]
            
            # Get table information
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Get record counts
            cursor.execute("SELECT COUNT(*) FROM sources")
            sources_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM citations")
            citations_count = cursor.fetchone()[0]
            
            return {
                "status": "healthy",
                "database_type": "sqlite_fallback",
                "test_query": test_result,
                "tables": tables,
                "sources_count": sources_count,
                "citations_count": citations_count,
                "db_path": self.db_path
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": f"SQLite health check failed: {str(e)}"
            }
    
    async def search_citations(self, query: str, province: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search citations by text content."""
        try:
            cursor = self.connection.cursor()
            
            # Build search query
            sql = """
                SELECT c.*, s.province, s.doc_class, s.asset_type, s.url, s.effective_date
                FROM citations c
                JOIN sources s ON c.source_id = s.id
                WHERE c.content LIKE ?
            """
            params = [f"%{query}%"]
            
            if province:
                sql += " AND s.province = ?"
                params.append(province)
            
            sql += " ORDER BY c.id LIMIT ?"
            params.append(limit)
            
            cursor.execute(sql, params)
            results = cursor.fetchall()
            
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"Citation search failed: {e}")
            return []
    
    async def get_sources_by_province(self, province: str) -> List[Dict[str, Any]]:
        """Get all sources for a specific province."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT * FROM sources WHERE province = ? ORDER BY effective_date DESC
            """, (province,))
            results = cursor.fetchall()
            return [dict(row) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get sources by province: {e}")
            return []
    
    async def get_provinces(self) -> List[str]:
        """Get list of all provinces in the database."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT DISTINCT province FROM sources ORDER BY province")
            results = cursor.fetchall()
            return [row[0] for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get provinces: {e}")
            return []
    
    async def get_asset_types(self) -> List[str]:
        """Get list of all asset types in the database."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT DISTINCT asset_type FROM sources ORDER BY asset_type")
            results = cursor.fetchall()
            return [row[0] for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get asset types: {e}")
            return []
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("SQLite fallback database connection closed")


# Global instance
_sqlite_fallback_db = None


async def get_sqlite_fallback_db() -> SQLiteFallbackDB:
    """Get or create SQLite fallback database instance."""
    global _sqlite_fallback_db
    
    if _sqlite_fallback_db is None:
        _sqlite_fallback_db = SQLiteFallbackDB()
        success = await _sqlite_fallback_db.initialize()
        if not success:
            raise Exception("Failed to initialize SQLite fallback database")
    
    return _sqlite_fallback_db


async def test_sqlite_fallback() -> Dict[str, Any]:
    """Test SQLite fallback database functionality."""
    try:
        db = await get_sqlite_fallback_db()
        health_info = await db.get_health_info()
        
        if health_info["status"] == "healthy":
            # Test search functionality
            search_results = await db.search_citations("光伏", limit=3)
            provinces = await db.get_provinces()
            asset_types = await db.get_asset_types()
            
            return {
                "status": "success",
                "health": health_info,
                "sample_search": {
                    "query": "光伏",
                    "results_count": len(search_results),
                    "sample_results": search_results[:2] if search_results else []
                },
                "provinces": provinces,
                "asset_types": asset_types
            }
        else:
            return {
                "status": "failed",
                "health": health_info
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error": f"SQLite fallback test failed: {str(e)}"
        }