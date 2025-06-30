"""
資料庫模型定義
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, JSON, Index, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class AnalysisRecord(Base):
    """分析記錄"""
    __tablename__ = 'analysis_records'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_type = Column(String(20), nullable=False)  # anr/tombstone
    analysis_mode = Column(String(20), nullable=False)  # quick/intelligent/large_file/max_token
    provider = Column(String(20), nullable=False)  # anthropic/openai
    model = Column(String(50), nullable=False)
    
    # 內容資訊
    content_hash = Column(String(64), nullable=False)  # SHA256 hash
    content_size = Column(Integer, nullable=False)  # bytes
    content_preview = Column(Text)  # 前 1000 字符
    
    # 分析結果
    result = Column(Text)
    result_size = Column(Integer)
    
    # 成本和使用統計
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    
    # 時間資訊
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    
    # 狀態
    status = Column(String(20), default='pending')  # pending/running/completed/failed/cancelled
    error_message = Column(Text)
    
    # 元資料 - 改名以避免與 SQLAlchemy 的 metadata 屬性衝突
    analysis_metadata = Column('metadata', JSON)  # Python 屬性名改為 analysis_metadata，但資料庫欄位名仍是 metadata
    
    # 索引
    __table_args__ = (
        Index('idx_content_hash', 'content_hash'),
        Index('idx_created_at', 'created_at'),
        Index('idx_status', 'status'),
        Index('idx_analysis_type_mode', 'analysis_type', 'analysis_mode'),
    )
    
    def to_dict(self):
        """轉換為字典"""
        return {
            'id': self.id,
            'analysis_type': self.analysis_type,
            'analysis_mode': self.analysis_mode,
            'provider': self.provider,
            'model': self.model,
            'content_size': self.content_size,
            'status': self.status,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_cost': self.total_cost,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'error_message': self.error_message,
            'metadata': self.analysis_metadata  # 注意這裡仍然輸出為 'metadata' 以保持 API 一致性
        }

class CostTracking(Base):
    """成本追蹤"""
    __tablename__ = 'cost_tracking'
    
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False, default=datetime.utcnow)
    provider = Column(String(20), nullable=False)
    model = Column(String(50), nullable=False)
    
    # 使用統計
    request_count = Column(Integer, default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    
    # 每日/每月彙總
    period_type = Column(String(10), default='daily')  # daily/monthly
    period_date = Column(DateTime, nullable=False)
    
    # 索引
    __table_args__ = (
        Index('idx_period', 'period_type', 'period_date'),
        Index('idx_provider_model', 'provider', 'model'),
    )

class ApiUsageLog(Base):
    """API 使用日誌"""
    __tablename__ = 'api_usage_logs'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # API 資訊
    provider = Column(String(20), nullable=False)
    model = Column(String(50), nullable=False)
    endpoint = Column(String(100))
    
    # 請求資訊
    request_id = Column(String(36))
    analysis_id = Column(String(36), ForeignKey('analysis_records.id'))
    
    # 使用統計
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    
    # 響應資訊
    status_code = Column(Integer)
    response_time_ms = Column(Integer)
    error_message = Column(Text)
    
    # 關聯
    analysis = relationship("AnalysisRecord", backref="api_logs")
    
    # 索引
    __table_args__ = (
        Index('idx_timestamp', 'timestamp'),
        Index('idx_analysis_id', 'analysis_id'),
    )

class UserSession(Base):
    """用戶會話"""
    __tablename__ = 'user_sessions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_token = Column(String(64), unique=True, nullable=False)
    
    # 用戶資訊
    user_id = Column(String(100))  # 可選的用戶標識
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    # 會話資訊
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # 使用統計
    analysis_count = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    
    # 配額
    budget_limit = Column(Float, default=10.0)
    budget_used = Column(Float, default=0.0)
    
    # 索引
    __table_args__ = (
        Index('idx_session_token', 'session_token'),
        Index('idx_user_id', 'user_id'),
        Index('idx_expires_at', 'expires_at'),
    )

class PromptHistory(Base):
    """Prompt 歷史記錄"""
    __tablename__ = 'prompt_history'
    
    id = Column(Integer, primary_key=True)
    analysis_id = Column(String(36), ForeignKey('analysis_records.id'))
    
    # Prompt 資訊
    prompt_key = Column(String(100))
    prompt_version = Column(String(20))
    
    # 內容
    system_prompt = Column(Text)
    user_prompt = Column(Text)
    variables = Column(JSON)
    
    # 時間
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 關聯
    analysis = relationship("AnalysisRecord", backref="prompts")

class SystemMetrics(Base):
    """系統指標"""
    __tablename__ = 'system_metrics'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 系統資源
    cpu_percent = Column(Float)
    memory_percent = Column(Float)
    disk_usage_percent = Column(Float)
    
    # 應用指標
    active_analyses = Column(Integer, default=0)
    queue_size = Column(Integer, default=0)
    cache_hit_rate = Column(Float)
    
    # API 健康
    api_availability = Column(Float)  # 0-100%
    average_response_time = Column(Float)  # ms
    error_rate = Column(Float)  # 0-100%
    
    # 索引
    __table_args__ = (
        Index('idx_metrics_timestamp', 'timestamp'),
    )

class ErrorLog(Base):
    """錯誤日誌"""
    __tablename__ = 'error_logs'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 錯誤資訊
    error_type = Column(String(100), nullable=False)
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text)
    
    # 上下文
    analysis_id = Column(String(36))
    user_session_id = Column(String(36))
    request_data = Column(JSON)
    
    # 嚴重性
    severity = Column(String(20), default='error')  # debug/info/warning/error/critical
    
    # 處理狀態
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)
    
    # 索引
    __table_args__ = (
        Index('idx_error_timestamp', 'timestamp'),
        Index('idx_error_type', 'error_type'),
        Index('idx_severity', 'severity'),
    )