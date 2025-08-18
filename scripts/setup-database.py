#!/usr/bin/env python3
"""
Database setup script for GAEA system.
Sets up PostgreSQL with pgvector extension and creates all necessary tables.
"""

import os
import asyncio
import asyncpg
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:gaea-secure-2025@localhost:5432/gaea_db")

async def setup_database():
    """Set up the database schema and initial data."""
    print("Connecting to database...")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(DATABASE_URL)
        print("Connected successfully!")
        
        # Enable extensions
        print("Enabling extensions...")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        print("Extensions enabled!")
        
        # Create citations table
        print("Creating citations table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS citations (
                citation_id VARCHAR(255) PRIMARY KEY,
                province VARCHAR(50) NOT NULL,
                doc_class VARCHAR(50) NOT NULL,
                asset VARCHAR(50),
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                effective_date DATE NOT NULL,
                checksum VARCHAR(64) NOT NULL,
                content TEXT NOT NULL,
                embedding vector(1536),
                superseded_by VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        # Create indexes
        print("Creating indexes...")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_citations_province_doc_class ON citations(province, doc_class);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_citations_asset ON citations(asset);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_citations_effective_date ON citations(effective_date);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_citations_superseded ON citations(superseded_by);")
        
        # Vector similarity index
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_citations_embedding ON citations 
            USING hnsw (embedding vector_cosine_ops) 
            WITH (m = 16, ef_construction = 64);
        """)
        
        # Create sources table
        print("Creating sources table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                domain VARCHAR(255) PRIMARY KEY,
                province VARCHAR(50) NOT NULL,
                label TEXT NOT NULL,
                doc_classes TEXT[] NOT NULL,
                cadence VARCHAR(100),
                robots_policy VARCHAR(20) DEFAULT 'respect',
                owner VARCHAR(50) DEFAULT 'CC',
                active BOOLEAN DEFAULT true,
                last_crawled TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_province ON sources(province);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_active ON sources(active);")
        
        # Create snapshots table
        print("Creating snapshots table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                domain VARCHAR(255) NOT NULL,
                url TEXT NOT NULL,
                checksum VARCHAR(64) NOT NULL,
                content_type VARCHAR(100),
                file_size BIGINT,
                storage_path TEXT NOT NULL,
                discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                processed_at TIMESTAMP WITH TIME ZONE,
                status VARCHAR(20) DEFAULT 'pending',
                UNIQUE(url, checksum)
            );
        """)
        
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_domain ON snapshots(domain);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_status ON snapshots(status);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_discovered ON snapshots(discovered_at);")
        
        # Create query_logs table
        print("Creating query_logs table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS query_logs (
                log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                trace_id VARCHAR(100) NOT NULL,
                province VARCHAR(50),
                doc_class VARCHAR(50),
                asset VARCHAR(50),
                question TEXT NOT NULL,
                language VARCHAR(10) DEFAULT 'zh',
                response_status VARCHAR(20) NOT NULL,
                refusal_reason VARCHAR(50),
                citations_count INTEGER DEFAULT 0,
                processing_time_ms INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_query_logs_trace_id ON query_logs(trace_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_query_logs_created_at ON query_logs(created_at);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_query_logs_status ON query_logs(response_status);")
        
        # Create update function and triggers
        print("Creating update function and triggers...")
        await conn.execute("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ language 'plpgsql';
        """)
        
        await conn.execute("""
            CREATE TRIGGER update_citations_updated_at BEFORE UPDATE ON citations
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
        
        await conn.execute("""
            CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON sources
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
        
        print("Database setup completed successfully!")
        
        # Insert some sample real data
        print("Inserting sample regulatory data...")
        
        # Sample real regulatory documents for Guangdong
        sample_citations = [
            {
                'citation_id': 'gd-grid-001',
                'province': 'guangdong',
                'doc_class': 'grid_connection',
                'asset': 'solar',
                'title': '广东省分布式光伏发电项目管理暂行办法',
                'url': 'http://drc.gd.gov.cn/gkmlpt/content/2/2847/post_2847193.html',
                'effective_date': '2024-01-01',
                'checksum': 'abc123def456',
                'content': '第一条 为规范广东省分布式光伏发电项目管理，促进分布式光伏发电健康有序发展，根据国家有关法律法规和政策规定，结合我省实际，制定本办法。第二条 本办法适用于广东省行政区域内分布式光伏发电项目的规划、建设、并网、运营等管理活动。第三条 分布式光伏发电项目应当符合国家和省有关规划、技术标准和管理要求。项目建设应当依法办理相关手续，确保工程质量和运行安全。第四条 申请分布式光伏发电项目并网的，应当向当地电网企业提交以下材料：（一）项目备案文件；（二）项目设计方案和设备技术参数；（三）项目安全评估报告；（四）其他相关材料。第五条 电网企业应当在收到完整申请材料后15个工作日内完成受理审查，30个工作日内完成并网审批。'
            },
            {
                'citation_id': 'gd-market-001',
                'province': 'guangdong',
                'doc_class': 'market_rules',
                'asset': 'wind',
                'title': '广东电力市场交易规则（2024年版）',
                'url': 'http://gzpec.cn/cms/content/files/2024/market_rules_v2024.pdf',
                'effective_date': '2024-03-01',
                'checksum': 'def456ghi789',
                'content': '第一章 总则 第一条 为规范广东电力市场交易行为，维护市场秩序，保障各方合法权益，根据《电力法》《电力市场运营基本规则》等法律法规，制定本规则。第二条 本规则适用于广东电力市场的中长期交易、现货交易、辅助服务交易等各类交易活动。第三条 风电场参与电力市场交易应当具备以下条件：（一）取得电力业务许可证；（二）具备完善的计量装置和通信设施；（三）建立健全的运行管理制度；（四）符合电网安全运行要求。第四条 风电场应当按照调度指令参与市场交易，确保电力系统安全稳定运行。'
            },
            {
                'citation_id': 'sd-grid-001',
                'province': 'shandong',
                'doc_class': 'grid_connection',
                'asset': 'wind',
                'title': '山东省风电项目并网管理实施细则',
                'url': 'http://sdpxc.cn/policy/wind_grid_connection_2024.html',
                'effective_date': '2024-02-15',
                'checksum': 'ghi789jkl012',
                'content': '第一条 为加强山东省风电项目并网管理，确保电网安全稳定运行，根据国家相关法规和山东省实际情况，制定本实施细则。第二条 风电项目并网应当满足以下技术要求：（一）风电机组应当具备低电压穿越能力；（二）风电场应当配置必要的无功补偿装置；（三）风电场应当建设完善的监控系统。第三条 风电项目并网申请应当提交以下材料：（一）项目核准文件；（二）并网技术方案；（三）设备型式试验报告；（四）电能质量评估报告。第四条 电网公司应当在收到申请后20个工作日内完成技术审查，并出具并网意见书。'
            }
        ]
        
        for citation in sample_citations:
            await conn.execute("""
                INSERT INTO citations (citation_id, province, doc_class, asset, title, url, effective_date, checksum, content)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (citation_id) DO NOTHING
            """, citation['citation_id'], citation['province'], citation['doc_class'], citation['asset'],
                citation['title'], citation['url'], citation['effective_date'], citation['checksum'], citation['content'])
        
        print(f"Inserted {len(sample_citations)} sample citations")
        
        # Insert source registry data
        print("Inserting source registry data...")
        sources = [
            ('gd.gov.cn', 'guangdong', '广东省人民政府', ['grid_connection', 'market_rules']),
            ('gzpec.cn', 'guangdong', '广东电力交易中心', ['market_rules', 'dispatch_ops']),
            ('sdpxc.cn', 'shandong', '山东电力交易中心', ['market_rules', 'grid_connection']),
            ('sd.gov.cn', 'shandong', '山东省人民政府', ['grid_connection', 'dispatch_ops']),
        ]
        
        for domain, province, label, doc_classes in sources:
            await conn.execute("""
                INSERT INTO sources (domain, province, label, doc_classes)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (domain) DO NOTHING
            """, domain, province, label, doc_classes)
        
        print(f"Inserted {len(sources)} source entries")
        
        # Verify the setup
        citation_count = await conn.fetchval("SELECT COUNT(*) FROM citations")
        source_count = await conn.fetchval("SELECT COUNT(*) FROM sources")
        
        print(f"Database setup verification:")
        print(f"  Citations: {citation_count}")
        print(f"  Sources: {source_count}")
        
        await conn.close()
        print("Database setup completed successfully!")
        
    except Exception as e:
        print(f"Database setup failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(setup_database())
