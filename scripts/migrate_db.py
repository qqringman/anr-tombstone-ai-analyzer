#!/usr/bin/env python3
"""
資料庫遷移腳本
使用 Alembic 進行資料庫版本管理
"""
import sys
import os
import argparse
from pathlib import Path
from alembic import command
from alembic.config import Config

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.database import init_db, close_db
from src.storage.models import Base
from src.config.system_config import get_system_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseMigrator:
    """資料庫遷移管理器"""
    
    def __init__(self, alembic_ini_path: str = None):
        """
        初始化遷移管理器
        
        Args:
            alembic_ini_path: Alembic 配置檔案路徑
        """
        self.project_root = Path(__file__).parent.parent
        
        if alembic_ini_path:
            self.alembic_cfg_path = Path(alembic_ini_path)
        else:
            self.alembic_cfg_path = self.project_root / "migrations" / "alembic.ini"
        
        if not self.alembic_cfg_path.exists():
            raise FileNotFoundError(f"Alembic config not found: {self.alembic_cfg_path}")
        
        # 設置 Alembic 配置
        self.alembic_cfg = Config(str(self.alembic_cfg_path))
        
        # 設置腳本位置
        script_location = str(self.project_root / "migrations")
        self.alembic_cfg.set_main_option("script_location", script_location)
        
        # 獲取系統配置
        self.config = get_system_config()
        
        # 設置資料庫 URL
        self.alembic_cfg.set_main_option(
            "sqlalchemy.url", 
            self.config.database.url
        )
    
    def init_alembic(self):
        """初始化 Alembic（只需執行一次）"""
        try:
            migrations_dir = self.project_root / "migrations"
            if not migrations_dir.exists():
                logger.info("Initializing Alembic...")
                command.init(self.alembic_cfg, str(migrations_dir))
                logger.info("Alembic initialized successfully")
            else:
                logger.info("Alembic already initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Alembic: {e}")
            raise
    
    def create_migration(self, message: str):
        """
        創建新的遷移腳本
        
        Args:
            message: 遷移描述
        """
        try:
            logger.info(f"Creating migration: {message}")
            command.revision(
                self.alembic_cfg,
                message=message,
                autogenerate=True
            )
            logger.info("Migration created successfully")
        except Exception as e:
            logger.error(f"Failed to create migration: {e}")
            raise
    
    def upgrade(self, revision: str = "head"):
        """
        升級資料庫到指定版本
        
        Args:
            revision: 目標版本（預設為最新版本）
        """
        try:
            logger.info(f"Upgrading database to {revision}")
            command.upgrade(self.alembic_cfg, revision)
            logger.info("Database upgraded successfully")
        except Exception as e:
            logger.error(f"Failed to upgrade database: {e}")
            raise
    
    def downgrade(self, revision: str = "-1"):
        """
        降級資料庫到指定版本
        
        Args:
            revision: 目標版本（預設為前一個版本）
        """
        try:
            logger.info(f"Downgrading database to {revision}")
            command.downgrade(self.alembic_cfg, revision)
            logger.info("Database downgraded successfully")
        except Exception as e:
            logger.error(f"Failed to downgrade database: {e}")
            raise
    
    def current(self):
        """顯示當前資料庫版本"""
        try:
            logger.info("Checking current database version")
            command.current(self.alembic_cfg)
        except Exception as e:
            logger.error(f"Failed to check current version: {e}")
            raise
    
    def history(self):
        """顯示遷移歷史"""
        try:
            logger.info("Showing migration history")
            command.history(self.alembic_cfg)
        except Exception as e:
            logger.error(f"Failed to show history: {e}")
            raise
    
    def stamp(self, revision: str):
        """
        標記資料庫為特定版本（不執行遷移）
        
        Args:
            revision: 版本號
        """
        try:
            logger.info(f"Stamping database with revision {revision}")
            command.stamp(self.alembic_cfg, revision)
            logger.info("Database stamped successfully")
        except Exception as e:
            logger.error(f"Failed to stamp database: {e}")
            raise
    
    def check_pending_migrations(self) -> bool:
        """
        檢查是否有待執行的遷移
        
        Returns:
            True 如果有待執行的遷移
        """
        try:
            # 使用 check 命令來檢查
            # 這會返回非零退出碼如果有待執行的遷移
            from alembic.script import ScriptDirectory
            from alembic.runtime.migration import MigrationContext
            from sqlalchemy import create_engine
            
            engine = create_engine(self.config.database.url)
            
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                script = ScriptDirectory.from_config(self.alembic_cfg)
                
                current_heads = context.get_current_heads()
                script_heads = script.get_heads()
                
                return current_heads != script_heads
                
        except Exception as e:
            logger.error(f"Failed to check pending migrations: {e}")
            raise
    
    def auto_upgrade(self):
        """自動執行所有待執行的遷移"""
        try:
            if self.check_pending_migrations():
                logger.info("Pending migrations found. Upgrading...")
                self.upgrade()
            else:
                logger.info("Database is up to date")
        except Exception as e:
            logger.error(f"Auto upgrade failed: {e}")
            raise


def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description='Database migration tool for ANR/Tombstone AI Analyzer'
    )
    
    parser.add_argument(
        'command',
        choices=[
            'init', 'create', 'upgrade', 'downgrade', 
            'current', 'history', 'stamp', 'check', 'auto'
        ],
        help='Migration command to execute'
    )
    
    parser.add_argument(
        '-m', '--message',
        help='Migration message (for create command)'
    )
    
    parser.add_argument(
        '-r', '--revision',
        help='Target revision'
    )
    
    parser.add_argument(
        '--alembic-ini',
        help='Path to alembic.ini file'
    )
    
    parser.add_argument(
        '--database-url',
        help='Override database URL from configuration'
    )
    
    args = parser.parse_args()
    
    # 設置資料庫 URL（如果提供）
    if args.database_url:
        os.environ['DATABASE_URL'] = args.database_url
    
    try:
        # 創建遷移管理器
        migrator = DatabaseMigrator(args.alembic_ini)
        
        # 執行命令
        if args.command == 'init':
            migrator.init_alembic()
            
        elif args.command == 'create':
            if not args.message:
                print("Error: Message is required for create command")
                sys.exit(1)
            migrator.create_migration(args.message)
            
        elif args.command == 'upgrade':
            revision = args.revision or 'head'
            migrator.upgrade(revision)
            
        elif args.command == 'downgrade':
            revision = args.revision or '-1'
            migrator.downgrade(revision)
            
        elif args.command == 'current':
            migrator.current()
            
        elif args.command == 'history':
            migrator.history()
            
        elif args.command == 'stamp':
            if not args.revision:
                print("Error: Revision is required for stamp command")
                sys.exit(1)
            migrator.stamp(args.revision)
            
        elif args.command == 'check':
            has_pending = migrator.check_pending_migrations()
            if has_pending:
                print("⚠️  There are pending migrations")
                sys.exit(1)
            else:
                print("✅ Database is up to date")
                
        elif args.command == 'auto':
            migrator.auto_upgrade()
        
        logger.info(f"Migration command '{args.command}' completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()