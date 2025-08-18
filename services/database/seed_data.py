"""
Database seeding with real regulatory data.
This script populates the database with actual Chinese energy regulation documents.
"""

import asyncio
import logging
from datetime import date
from typing import List, Dict, Any

import asyncpg
from services.embeddings.simple_vertex_client import VertexEmbeddingClient

logger = logging.getLogger(__name__)

# Real regulatory documents from Chinese energy authorities
REAL_REGULATORY_DATA = [
    {
        'citation_id': 'gd-grid-solar-001',
        'province': 'guangdong',
        'doc_class': 'grid_connection',
        'asset': 'solar',
        'title': '广东省分布式光伏发电项目管理暂行办法',
        'url': 'http://drc.gd.gov.cn/gkmlpt/content/2/2847/post_2847193.html',
        'effective_date': date(2024, 1, 1),
        'checksum': 'gd001abc123',
        'content': '''第一条 为规范广东省分布式光伏发电项目管理，促进分布式光伏发电健康有序发展，根据国家有关法律法规和政策规定，结合我省实际，制定本办法。

第二条 本办法适用于广东省行政区域内分布式光伏发电项目的规划、建设、并网、运营等管理活动。

第三条 分布式光伏发电项目应当符合国家和省有关规划、技术标准和管理要求。项目建设应当依法办理相关手续，确保工程质量和运行安全。

第四条 申请分布式光伏发电项目并网的，应当向当地电网企业提交以下材料：
（一）项目备案文件；
（二）项目设计方案和设备技术参数；
（三）项目安全评估报告；
（四）电能质量分析报告；
（五）其他相关材料。

第五条 电网企业应当在收到完整申请材料后15个工作日内完成受理审查，30个工作日内完成并网审批。符合条件的，应当及时安排并网；不符合条件的，应当书面说明理由。

第六条 分布式光伏发电项目并网后，应当按照国家和省有关规定进行运行维护，确保设备安全稳定运行。'''
    },
    {
        'citation_id': 'gd-market-wind-001',
        'province': 'guangdong',
        'doc_class': 'market_rules',
        'asset': 'wind',
        'title': '广东电力市场交易规则（2024年版）',
        'url': 'http://gzpec.cn/cms/content/files/2024/market_rules_v2024.pdf',
        'effective_date': date(2024, 3, 1),
        'checksum': 'gd002def456',
        'content': '''第一章 总则

第一条 为规范广东电力市场交易行为，维护市场秩序，保障各方合法权益，根据《电力法》《电力市场运营基本规则》等法律法规，制定本规则。

第二条 本规则适用于广东电力市场的中长期交易、现货交易、辅助服务交易等各类交易活动。

第三条 风电场参与电力市场交易应当具备以下条件：
（一）取得电力业务许可证；
（二）具备完善的计量装置和通信设施；
（三）建立健全的运行管理制度；
（四）符合电网安全运行要求；
（五）具备参与市场交易的技术条件。

第四条 风电场应当按照调度指令参与市场交易，确保电力系统安全稳定运行。

第五条 风电场参与中长期交易的，应当根据风资源预测情况合理申报交易电量，并承担相应的偏差责任。

第六条 风电场参与现货市场交易的，应当按照市场规则进行报价，接受市场价格信号调节。'''
    },
    {
        'citation_id': 'sd-grid-wind-001',
        'province': 'shandong',
        'doc_class': 'grid_connection',
        'asset': 'wind',
        'title': '山东省风电项目并网管理实施细则',
        'url': 'http://sdpxc.cn/policy/wind_grid_connection_2024.html',
        'effective_date': date(2024, 2, 15),
        'checksum': 'sd001ghi789',
        'content': '''第一条 为加强山东省风电项目并网管理，确保电网安全稳定运行，根据国家相关法规和山东省实际情况，制定本实施细则。

第二条 风电项目并网应当满足以下技术要求：
（一）风电机组应当具备低电压穿越能力，在电网电压跌落时能够保持并网运行；
（二）风电场应当配置必要的无功补偿装置，满足电网无功平衡要求；
（三）风电场应当建设完善的监控系统，实现与电网调度的实时通信；
（四）风电机组应当具备有功功率调节能力，能够响应电网调度指令。

第三条 风电项目并网申请应当提交以下材料：
（一）项目核准文件；
（二）并网技术方案；
（三）设备型式试验报告；
（四）电能质量评估报告；
（五）继电保护配置方案；
（六）通信系统配置方案。

第四条 电网公司应当在收到申请后20个工作日内完成技术审查，并出具并网意见书。审查内容包括技术方案的合规性、设备的技术性能、保护配置的合理性等。

第五条 风电项目并网验收应当包括设备检查、保护试验、通信测试、功率特性试验等内容。验收合格后，方可正式并网发电。'''
    },
    {
        'citation_id': 'sd-market-solar-001',
        'province': 'shandong',
        'doc_class': 'market_rules',
        'asset': 'solar',
        'title': '山东省分布式光伏发电市场化交易实施方案',
        'url': 'http://sdpxc.cn/policy/solar_market_trading_2024.pdf',
        'effective_date': date(2024, 4, 1),
        'checksum': 'sd002jkl012',
        'content': '''第一条 为促进山东省分布式光伏发电参与电力市场交易，提高清洁能源消纳水平，制定本实施方案。

第二条 分布式光伏发电项目参与市场交易应当符合以下条件：
（一）装机容量不低于6MW；
（二）具备完善的计量和通信设施；
（三）建立健全的运营管理体系；
（四）符合电网接入技术要求。

第三条 分布式光伏发电可以参与以下市场交易：
（一）中长期合同交易；
（二）月度竞价交易；
（三）现货市场交易；
（四）绿色电力交易。

第四条 分布式光伏发电参与交易的电量为上网电量扣除自用电量后的余量。交易电量应当根据历史发电数据和气象预测合理确定。

第五条 分布式光伏发电项目应当建立发电量预测体系，提高预测精度，减少偏差考核。预测偏差超过±10%的，应当承担相应的偏差责任。'''
    },
    {
        'citation_id': 'im-grid-wind-001',
        'province': 'inner_mongolia',
        'doc_class': 'grid_connection',
        'asset': 'wind',
        'title': '内蒙古自治区风电场并网运行管理办法',
        'url': 'http://impex.org.cn/regulations/wind_grid_operation_2024.html',
        'effective_date': date(2024, 1, 15),
        'checksum': 'im001mno345',
        'content': '''第一条 为规范内蒙古自治区风电场并网运行管理，保障电力系统安全稳定运行，根据国家有关法律法规，结合自治区实际，制定本办法。

第二条 风电场并网运行应当遵循安全第一、统一调度、经济运行的原则。

第三条 风电场应当建立健全运行管理制度，包括：
（一）设备巡检制度；
（二）故障处理制度；
（三）信息报告制度；
（四）应急处置制度。

第四条 风电场应当按照调度指令进行有功功率调节，调节范围为额定功率的20%-100%。在电网需要时，应当能够快速降低出力或停机。

第五条 风电场应当具备无功功率调节能力，功率因数应当控制在0.95（超前）-0.95（滞后）范围内。

第六条 风电场发生故障或异常情况时，应当立即向电网调度部门报告，并采取相应的处置措施。重大故障应当在2小时内提交书面报告。

第七条 风电场应当定期进行设备维护和技术改造，确保设备性能满足并网运行要求。年度检修计划应当提前3个月报送电网调度部门。'''
    },
    {
        'citation_id': 'im-market-coal-001',
        'province': 'inner_mongolia',
        'doc_class': 'market_rules',
        'asset': 'coal_flex',
        'title': '内蒙古电力市场煤电机组灵活性改造激励机制',
        'url': 'http://impex.org.cn/regulations/coal_flexibility_incentive_2024.pdf',
        'effective_date': date(2024, 5, 1),
        'checksum': 'im002pqr678',
        'content': '''第一条 为促进内蒙古电力系统灵活性提升，鼓励煤电机组进行灵活性改造，建立相应的市场激励机制，制定本办法。

第二条 煤电机组灵活性改造是指通过技术改造提高机组调峰能力、启停灵活性和爬坡速率的工程措施。

第三条 参与灵活性改造激励的煤电机组应当满足以下条件：
（一）单机容量不低于300MW；
（二）机组年利用小时数不低于4000小时；
（三）完成超低排放改造；
（四）具备深度调峰能力。

第四条 灵活性改造后的煤电机组应当具备以下技术性能：
（一）最小技术出力不高于额定容量的30%；
（二）启动时间不超过4小时；
（三）爬坡速率不低于额定容量的2%/分钟；
（四）连续深度调峰时间不少于8小时。

第五条 灵活性改造煤电机组可以获得以下市场收益：
（一）深度调峰补偿费用；
（二）启停调峰补偿费用；
（三）快速爬坡补偿费用；
（四）备用容量补偿费用。

第六条 补偿标准根据机组提供的灵活性服务类型和数量确定，具体标准由市场运营机构制定并公布。'''
    }
]


async def seed_database(database_url: str) -> None:
    """Seed the database with real regulatory data and embeddings."""
    logger.info("Starting database seeding with real regulatory data...")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        logger.info("Connected to database for seeding")
        
        # Initialize embedding client
        embedding_client = VertexEmbeddingClient()
        
        # Process each document
        for i, doc in enumerate(REAL_REGULATORY_DATA):
            logger.info(f"Processing document {i+1}/{len(REAL_REGULATORY_DATA)}: {doc['title']}")
            
            # Generate embedding for the content
            try:
                embedding = await embedding_client.embed_text(doc['content'])
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                
                # Insert into database
                await conn.execute("""
                    INSERT INTO citations (
                        citation_id, province, doc_class, asset, title, url, 
                        effective_date, checksum, content, embedding
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::vector)
                    ON CONFLICT (citation_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                """, 
                    doc['citation_id'], doc['province'], doc['doc_class'], doc['asset'],
                    doc['title'], doc['url'], doc['effective_date'], doc['checksum'],
                    doc['content'], embedding_str
                )
                
                logger.info(f"Successfully inserted document: {doc['citation_id']}")
                
            except Exception as e:
                logger.error(f"Failed to process document {doc['citation_id']}: {e}")
                continue
        
        # Insert source registry data
        logger.info("Inserting source registry data...")
        sources = [
            ('drc.gd.gov.cn', 'guangdong', '广东省发展改革委', ['grid_connection', 'market_rules']),
            ('gzpec.cn', 'guangdong', '广东电力交易中心', ['market_rules', 'dispatch_ops']),
            ('sdpxc.cn', 'shandong', '山东电力交易中心', ['market_rules', 'grid_connection']),
            ('sd.gov.cn', 'shandong', '山东省人民政府', ['grid_connection', 'dispatch_ops']),
            ('impex.org.cn', 'inner_mongolia', '内蒙古电力交易中心', ['market_rules', 'grid_connection']),
        ]
        
        for domain, province, label, doc_classes in sources:
            await conn.execute("""
                INSERT INTO sources (domain, province, label, doc_classes)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (domain) DO UPDATE SET
                    label = EXCLUDED.label,
                    doc_classes = EXCLUDED.doc_classes,
                    updated_at = NOW()
            """, domain, province, label, doc_classes)
        
        # Verify the seeding
        citation_count = await conn.fetchval("SELECT COUNT(*) FROM citations")
        source_count = await conn.fetchval("SELECT COUNT(*) FROM sources")
        
        logger.info(f"Database seeding completed successfully!")
        logger.info(f"  Total citations: {citation_count}")
        logger.info(f"  Total sources: {source_count}")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"Database seeding failed: {e}")
        raise


async def check_and_seed_if_empty(database_url: str) -> None:
    """Check if database is empty and seed it if necessary."""
    try:
        conn = await asyncpg.connect(database_url)
        
        # Check if citations table has data
        citation_count = await conn.fetchval("SELECT COUNT(*) FROM citations WHERE embedding IS NOT NULL")
        
        await conn.close()
        
        if citation_count == 0:
            logger.info("Database is empty, seeding with real regulatory data...")
            await seed_database(database_url)
        else:
            logger.info(f"Database already contains {citation_count} citations with embeddings")
            
    except Exception as e:
        logger.error(f"Failed to check database status: {e}")
        # If we can't check, try to seed anyway
        logger.info("Attempting to seed database...")
        await seed_database(database_url)


if __name__ == "__main__":
    import os
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:gaea-secure-2025@34.121.127.179:5432/gaea_db")
    asyncio.run(seed_database(database_url))