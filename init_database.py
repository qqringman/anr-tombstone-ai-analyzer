#!/usr/bin/env python3
"""
ANR/Tombstone AI 分析系統 - 數據庫初始化腳本

使用方法:
    python init_database.py                    # 使用預設配置初始化
    python init_database.py --drop            # 先刪除所有表再重建
    python init_database.py --test-data       # 初始化並插入測試數據
    python init_database.py --check           # 檢查數據庫連接和表結構
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from src.storage.models import Base, AnalysisRecord, CostTracking, ApiUsageLog, UserSession, PromptHistory, SystemMetrics, ErrorLog
from src.storage.database import Database, init_db, close_db
from src.config.system_config import SystemConfig, get_system_config

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseInitializer:
    """數據庫初始化器"""
    
    def __init__(self, config_path: str = None):
        """初始化"""
        # 載入配置
        if config_path:
            self.config = SystemConfig.from_yaml(config_path)
        else:
            self.config = get_system_config()
        
        self.database_url = self.config.database.url
        logger.info(f"使用數據庫: {self._mask_connection_string(self.database_url)}")
    
    def _mask_connection_string(self, url: str) -> str:
        """遮蔽連接字串中的敏感資訊"""
        if '@' in url:
            parts = url.split('@')
            if len(parts) >= 2:
                return f"{parts[0].split('://')[0]}://****@{parts[1]}"
        return url
    
    def check_connection(self) -> bool:
        """檢查數據庫連接"""
        try:
            engine = create_engine(self.database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✓ 數據庫連接成功")
            return True
        except Exception as e:
            logger.error(f"✗ 數據庫連接失敗: {e}")
            return False
    
    def create_database_if_not_exists(self):
        """如果數據庫不存在則創建（僅適用於 PostgreSQL）"""
        if 'postgresql' in self.database_url:
            try:
                # 解析數據庫名稱
                db_name = self.database_url.split('/')[-1].split('?')[0]
                
                # 連接到預設數據庫
                temp_url = self.database_url.rsplit('/', 1)[0] + '/postgres'
                engine = create_engine(temp_url)
                
                with engine.connect() as conn:
                    # 檢查數據庫是否存在
                    exists = conn.execute(
                        text("SELECT 1 FROM pg_database WHERE datname = :name"),
                        {"name": db_name}
                    ).fetchone()
                    
                    if not exists:
                        # 創建數據庫
                        conn.execute(text(f"CREATE DATABASE {db_name}"))
                        logger.info(f"✓ 創建數據庫: {db_name}")
                    else:
                        logger.info(f"✓ 數據庫已存在: {db_name}")
                        
            except Exception as e:
                logger.warning(f"無法自動創建數據庫: {e}")
    
    def init_tables(self, drop_existing: bool = False):
        """初始化數據表"""
        try:
            db = Database(self.database_url)
            db.initialize()
            
            if drop_existing:
                logger.warning("正在刪除所有現有表...")
                db.drop_tables()
                logger.info("✓ 所有表已刪除")
            
            logger.info("正在創建數據表...")
            db.create_tables()
            logger.info("✓ 所有表已創建")
            
            # 驗證表結構
            self.verify_tables(db.engine)
            
            db.close()
            
        except Exception as e:
            logger.error(f"初始化表失敗: {e}")
            raise
    
    def verify_tables(self, engine):
        """驗證表結構"""
        inspector = inspect(engine)
        expected_tables = [
            'analysis_records',
            'cost_tracking',
            'api_usage_logs',
            'user_sessions',
            'prompt_history',
            'system_metrics',
            'error_logs'
        ]
        
        existing_tables = inspector.get_table_names()
        
        logger.info("\n表結構驗證:")
        for table in expected_tables:
            if table in existing_tables:
                # 獲取列數
                columns = inspector.get_columns(table)
                logger.info(f"  ✓ {table} ({len(columns)} 列)")
            else:
                logger.error(f"  ✗ {table} 不存在")
    
    def insert_test_data(self):
        """插入測試數據"""
        logger.info("\n插入測試數據...")
        
        db = Database(self.database_url)
        db.initialize()
        
        with db.session() as session:
            try:
                # 1. 創建測試分析記錄
                test_analysis = AnalysisRecord(
                    id="test-analysis-001",
                    analysis_type="anr",
                    analysis_mode="intelligent",
                    provider="anthropic",
                    model="claude-sonnet-4",
                    content_hash="test_hash_001",
                    content_size=5120,
                    content_preview="Test ANR log content...",
                    result="# ANR 分析結果\n\n## 問題摘要\n主線程被阻塞...",
                    result_size=2048,
                    input_tokens=1000,
                    output_tokens=500,
                    total_cost=0.15,
                    status="completed",
                    created_at=datetime.utcnow() - timedelta(hours=1),
                    started_at=datetime.utcnow() - timedelta(hours=1),
                    completed_at=datetime.utcnow() - timedelta(minutes=50),
                    duration_seconds=600
                )
                session.add(test_analysis)
                
                # 2. 創建成本追蹤記錄
                cost_tracking = CostTracking(
                    provider="anthropic",
                    model="claude-sonnet-4",
                    period_type="daily",
                    period_date=datetime.utcnow().replace(hour=0, minute=0, second=0),
                    request_count=10,
                    input_tokens=10000,
                    output_tokens=5000,
                    total_cost=1.5
                )
                session.add(cost_tracking)
                
                # 3. 創建API使用日誌
                api_log = ApiUsageLog(
                    provider="anthropic",
                    model="claude-sonnet-4",
                    analysis_id="test-analysis-001",
                    input_tokens=1000,
                    output_tokens=500,
                    cost=0.15,
                    status_code=200,
                    response_time_ms=1500
                )
                session.add(api_log)
                
                # 4. 創建用戶會話
                user_session = UserSession(
                    id="test-session-001",
                    session_token="test_token_12345",
                    ip_address="127.0.0.1",
                    user_agent="Mozilla/5.0 Test Browser",
                    analysis_count=5,
                    total_cost=0.75,
                    budget_used=0.75
                )
                session.add(user_session)
                
                # 5. 創建系統指標
                system_metrics = SystemMetrics(
                    cpu_percent=25.5,
                    memory_percent=45.2,
                    disk_usage_percent=60.0,
                    active_analyses=2,
                    queue_size=5,
                    cache_hit_rate=85.5,
                    api_availability=99.9,
                    average_response_time=1200,
                    error_rate=0.1
                )
                session.add(system_metrics)
                
                session.commit()
                logger.info("✓ 測試數據插入成功")
                
            except Exception as e:
                session.rollback()
                logger.error(f"插入測試數據失敗: {e}")
                raise
        
        db.close()
    
    def show_statistics(self):
        """顯示數據庫統計資訊"""
        db = Database(self.database_url)
        db.initialize()
        
        with db.session() as session:
            stats = {
                "分析記錄": session.query(AnalysisRecord).count(),
                "成本追蹤": session.query(CostTracking).count(),
                "API日誌": session.query(ApiUsageLog).count(),
                "用戶會話": session.query(UserSession).count(),
                "Prompt歷史": session.query(PromptHistory).count(),
                "系統指標": session.query(SystemMetrics).count(),
                "錯誤日誌": session.query(ErrorLog).count()
            }
            
            logger.info("\n數據庫統計:")
            for table, count in stats.items():
                logger.info(f"  {table}: {count} 條記錄")
            
            # 獲取最近的分析
            recent_analyses = session.query(AnalysisRecord)\
                .order_by(AnalysisRecord.created_at.desc())\
                .limit(5)\
                .all()
            
            if recent_analyses:
                logger.info("\n最近的分析:")
                for analysis in recent_analyses:
                    logger.info(f"  - {analysis.id}: {analysis.analysis_type} ({analysis.status}) - {analysis.created_at}")
        
        db.close()

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='ANR/Tombstone AI 分析系統數據庫初始化')
    parser.add_argument('--config', help='配置檔案路徑', default=None)
    parser.add_argument('--drop', action='store_true', help='刪除現有表並重建')
    parser.add_argument('--test-data', action='store_true', help='插入測試數據')
    parser.add_argument('--check', action='store_true', help='僅檢查連接和表結構')
    parser.add_argument('--stats', action='store_true', help='顯示數據庫統計')
    
    args = parser.parse_args()
    
    # 載入環境變數
    from dotenv import load_dotenv
    load_dotenv()
    
    # 創建初始化器
    initializer = DatabaseInitializer(args.config)
    
    try:
        # 檢查連接
        if not initializer.check_connection():
            logger.error("無法連接到數據庫，請檢查配置")
            sys.exit(1)
        
        if args.check:
            # 僅檢查
            db = Database(initializer.database_url)
            db.initialize()
            initializer.verify_tables(db.engine)
            db.close()
        elif args.stats:
            # 顯示統計
            initializer.show_statistics()
        else:
            # 創建數據庫（如果需要）
            initializer.create_database_if_not_exists()
            
            # 初始化表
            initializer.init_tables(drop_existing=args.drop)
            
            # 插入測試數據
            if args.test_data:
                initializer.insert_test_data()
            
            # 顯示統計
            initializer.show_statistics()
            
            logger.info("\n✅ 數據庫初始化完成!")
            
    except Exception as e:
        logger.error(f"\n❌ 初始化失敗: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()