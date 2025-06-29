#!/usr/bin/env python3
"""
資料庫初始化腳本
"""
import sys
import os
from pathlib import Path

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.database import init_db, close_db
from src.storage.models import Base
from src.config.system_config import get_system_config
from src.utils.logger import get_logger

logger = get_logger(__name__)

def setup_database(drop_existing: bool = False):
    """
    設置資料庫
    
    Args:
        drop_existing: 是否刪除現有資料表
    """
    try:
        logger.info("Starting database setup...")
        
        # 獲取配置
        config = get_system_config()
        database_url = config.database.url
        
        logger.info(f"Database URL: {database_url}")
        
        # 初始化資料庫
        db = init_db(database_url)
        
        if drop_existing:
            logger.warning("Dropping existing tables...")
            db.drop_tables()
        
        # 創建資料表
        logger.info("Creating database tables...")
        db.create_tables()
        
        # 驗證
        if db.health_check():
            logger.info("Database setup completed successfully!")
            logger.info("Tables created:")
            
            # 列出所有資料表
            for table in Base.metadata.tables.keys():
                logger.info(f"  - {table}")
        else:
            logger.error("Database health check failed!")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        return False
    finally:
        close_db()

def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup database for ANR/Tombstone AI Analyzer')
    parser.add_argument(
        '--drop-existing',
        action='store_true',
        help='Drop existing tables before creating new ones'
    )
    parser.add_argument(
        '--database-url',
        help='Override database URL from configuration'
    )
    
    args = parser.parse_args()
    
    # 如果提供了資料庫 URL，設置環境變數
    if args.database_url:
        os.environ['DATABASE_URL'] = args.database_url
    
    # 確認刪除操作
    if args.drop_existing:
        response = input("⚠️  WARNING: This will delete all existing data. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Operation cancelled.")
            sys.exit(0)
    
    # 執行設置
    success = setup_database(drop_existing=args.drop_existing)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()