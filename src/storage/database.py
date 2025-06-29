"""
資料庫連接管理
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Optional, Generator
import logging

from .models import Base
from ..config.system_config import get_system_config

logger = logging.getLogger(__name__)

class Database:
    """資料庫管理器"""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        初始化資料庫
        
        Args:
            database_url: 資料庫連接字串
        """
        if database_url is None:
            config = get_system_config()
            database_url = config.database.url
        
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None
        self._initialized = False
    
    def initialize(self):
        """初始化資料庫連接"""
        if self._initialized:
            return
        
        try:
            # 創建引擎
            config = get_system_config()
            
            # SQLite 特殊處理
            if self.database_url.startswith('sqlite'):
                self.engine = create_engine(
                    self.database_url,
                    connect_args={"check_same_thread": False},
                    echo=config.database.echo
                )
                
                # 啟用外鍵約束
                @event.listens_for(self.engine, "connect")
                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.close()
            else:
                # PostgreSQL/MySQL
                self.engine = create_engine(
                    self.database_url,
                    poolclass=QueuePool,
                    pool_size=config.database.pool_size,
                    max_overflow=config.database.max_overflow,
                    pool_pre_ping=True,
                    echo=config.database.echo
                )
            
            # 創建會話工廠
            self.SessionLocal = scoped_session(
                sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=self.engine
                )
            )
            
            self._initialized = True
            logger.info(f"Database initialized: {self._mask_connection_string(self.database_url)}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def create_tables(self):
        """創建所有資料表"""
        if not self._initialized:
            self.initialize()
        
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    def drop_tables(self):
        """刪除所有資料表"""
        if not self._initialized:
            self.initialize()
        
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            raise
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """獲取資料庫會話的上下文管理器"""
        if not self._initialized:
            self.initialize()
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_session(self) -> Session:
        """獲取資料庫會話"""
        if not self._initialized:
            self.initialize()
        
        return self.SessionLocal()
    
    def close_session(self):
        """關閉會話"""
        if self.SessionLocal:
            self.SessionLocal.remove()
    
    def close(self):
        """關閉資料庫連接"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")
    
    def health_check(self) -> bool:
        """健康檢查"""
        if not self._initialized:
            return False
        
        try:
            with self.session() as session:
                session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def _mask_connection_string(self, url: str) -> str:
        """遮蔽連接字串中的敏感資訊"""
        if '@' in url:
            # 提取並遮蔽密碼部分
            parts = url.split('@')
            if len(parts) >= 2:
                auth_part = parts[0]
                if ':' in auth_part:
                    # 找到密碼部分
                    protocol_user = auth_part.rsplit(':', 1)[0]
                    return f"{protocol_user}:****@{parts[1]}"
        return url

# 全局資料庫實例
_db: Optional[Database] = None

def get_db() -> Database:
    """獲取全局資料庫實例"""
    global _db
    if _db is None:
        _db = Database()
    return _db

def init_db(database_url: Optional[str] = None):
    """初始化資料庫"""
    global _db
    _db = Database(database_url)
    _db.initialize()
    _db.create_tables()
    return _db

def close_db():
    """關閉資料庫"""
    global _db
    if _db:
        _db.close()
        _db = None

# 依賴注入函數（用於 FastAPI/Flask）
def get_db_session() -> Generator[Session, None, None]:
    """獲取資料庫會話（用於依賴注入）"""
    db = get_db()
    with db.session() as session:
        yield session