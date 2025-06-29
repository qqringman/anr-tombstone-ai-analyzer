"""
結果儲存管理器
"""
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from .models import (
    AnalysisRecord, CostTracking, ApiUsageLog, 
    UserSession, SystemMetrics, ErrorLog
)
from .database import get_db
from ..config.base import AnalysisMode, ModelProvider
from ..utils.logger import get_logger

logger = get_logger(__name__)

class ResultStorage:
    """結果儲存管理器"""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        初始化儲存管理器
        
        Args:
            database_url: 資料庫連接字串
        """
        self.db = get_db()
        if database_url:
            self.db.database_url = database_url
        self.db.initialize()
    
    def _calculate_content_hash(self, content: str) -> str:
        """計算內容的 SHA256 hash"""
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def create_analysis_record(self,
                                   analysis_type: str,
                                   analysis_mode: str,
                                   provider: str,
                                   model: str,
                                   content: str,
                                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """創建分析記錄"""
        with self.db.session() as session:
            record = AnalysisRecord(
                analysis_type=analysis_type,
                analysis_mode=analysis_mode,
                provider=provider,
                model=model,
                content_hash=self._calculate_content_hash(content),
                content_size=len(content.encode()),
                content_preview=content[:1000],
                metadata=metadata or {}
            )
            
            session.add(record)
            session.commit()
            
            logger.info(f"Created analysis record: {record.id}")
            return record.id
    
    async def update_analysis_result(self,
                                   analysis_id: str,
                                   result: str,
                                   input_tokens: int,
                                   output_tokens: int,
                                   cost: float,
                                   status: str = 'completed'):
        """更新分析結果"""
        with self.db.session() as session:
            record = session.query(AnalysisRecord).filter_by(id=analysis_id).first()
            
            if record:
                record.result = result
                record.result_size = len(result.encode()) if result else 0
                record.input_tokens = input_tokens
                record.output_tokens = output_tokens
                record.total_cost = cost
                record.status = status
                record.completed_at = datetime.utcnow()
                
                if record.started_at:
                    duration = (record.completed_at - record.started_at).total_seconds()
                    record.duration_seconds = duration
                
                session.commit()
                logger.info(f"Updated analysis result: {analysis_id}")
    
    async def update_analysis_status(self,
                                   analysis_id: str,
                                   status: str,
                                   error_message: Optional[str] = None):
        """更新分析狀態"""
        with self.db.session() as session:
            record = session.query(AnalysisRecord).filter_by(id=analysis_id).first()
            
            if record:
                record.status = status
                if error_message:
                    record.error_message = error_message
                
                if status == 'running' and not record.started_at:
                    record.started_at = datetime.utcnow()
                elif status in ['completed', 'failed', 'cancelled']:
                    record.completed_at = datetime.utcnow()
                    if record.started_at:
                        duration = (record.completed_at - record.started_at).total_seconds()
                        record.duration_seconds = duration
                
                session.commit()
    
    async def get_analysis_record(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """獲取分析記錄"""
        with self.db.session() as session:
            record = session.query(AnalysisRecord).filter_by(id=analysis_id).first()
            return record.to_dict() if record else None
    
    async def find_cached_result(self,
                               content: str,
                               analysis_type: str,
                               analysis_mode: str,
                               provider: str,
                               max_age_hours: int = 24) -> Optional[str]:
        """查找快取的結果"""
        content_hash = self._calculate_content_hash(content)
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        with self.db.session() as session:
            record = session.query(AnalysisRecord).filter(
                and_(
                    AnalysisRecord.content_hash == content_hash,
                    AnalysisRecord.analysis_type == analysis_type,
                    AnalysisRecord.analysis_mode == analysis_mode,
                    AnalysisRecord.provider == provider,
                    AnalysisRecord.status == 'completed',
                    AnalysisRecord.created_at > cutoff_time
                )
            ).order_by(AnalysisRecord.created_at.desc()).first()
            
            return record.result if record else None
    
    async def track_api_usage(self,
                            provider: str,
                            model: str,
                            input_tokens: int,
                            output_tokens: int,
                            cost: float,
                            analysis_id: Optional[str] = None,
                            status_code: Optional[int] = None,
                            response_time_ms: Optional[int] = None,
                            error_message: Optional[str] = None):
        """追蹤 API 使用"""
        with self.db.session() as session:
            log = ApiUsageLog(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                analysis_id=analysis_id,
                status_code=status_code,
                response_time_ms=response_time_ms,
                error_message=error_message
            )
            session.add(log)
            
            # 更新每日成本追蹤
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            daily_tracking = session.query(CostTracking).filter(
                and_(
                    CostTracking.provider == provider,
                    CostTracking.model == model,
                    CostTracking.period_type == 'daily',
                    CostTracking.period_date == today
                )
            ).first()
            
            if daily_tracking:
                daily_tracking.request_count += 1
                daily_tracking.input_tokens += input_tokens
                daily_tracking.output_tokens += output_tokens
                daily_tracking.total_cost += cost
            else:
                daily_tracking = CostTracking(
                    provider=provider,
                    model=model,
                    period_type='daily',
                    period_date=today,
                    request_count=1,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_cost=cost
                )
                session.add(daily_tracking)
            
            session.commit()
    
    async def get_cost_statistics(self,
                                start_date: Optional[datetime] = None,
                                end_date: Optional[datetime] = None,
                                provider: Optional[str] = None) -> Dict[str, Any]:
        """獲取成本統計"""
        with self.db.session() as session:
            query = session.query(CostTracking).filter(
                CostTracking.period_type == 'daily'
            )
            
            if start_date:
                query = query.filter(CostTracking.period_date >= start_date)
            if end_date:
                query = query.filter(CostTracking.period_date <= end_date)
            if provider:
                query = query.filter(CostTracking.provider == provider)
            
            records = query.all()
            
            # 彙總統計
            total_cost = sum(r.total_cost for r in records)
            total_requests = sum(r.request_count for r in records)
            total_input_tokens = sum(r.input_tokens for r in records)
            total_output_tokens = sum(r.output_tokens for r in records)
            
            # 按提供者分組
            by_provider = {}
            for record in records:
                if record.provider not in by_provider:
                    by_provider[record.provider] = {
                        'cost': 0,
                        'requests': 0,
                        'input_tokens': 0,
                        'output_tokens': 0
                    }
                
                by_provider[record.provider]['cost'] += record.total_cost
                by_provider[record.provider]['requests'] += record.request_count
                by_provider[record.provider]['input_tokens'] += record.input_tokens
                by_provider[record.provider]['output_tokens'] += record.output_tokens
            
            return {
                'total_cost': total_cost,
                'total_requests': total_requests,
                'total_input_tokens': total_input_tokens,
                'total_output_tokens': total_output_tokens,
                'by_provider': by_provider,
                'daily_records': [
                    {
                        'date': r.period_date.isoformat(),
                        'provider': r.provider,
                        'model': r.model,
                        'cost': r.total_cost,
                        'requests': r.request_count
                    }
                    for r in records
                ]
            }
    
    async def create_user_session(self,
                                session_token: str,
                                user_id: Optional[str] = None,
                                ip_address: Optional[str] = None,
                                user_agent: Optional[str] = None,
                                budget_limit: float = 10.0) -> str:
        """創建用戶會話"""
        with self.db.session() as session:
            user_session = UserSession(
                session_token=session_token,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                budget_limit=budget_limit,
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            session.add(user_session)
            session.commit()
            
            return user_session.id
    
    async def update_user_session_usage(self,
                                      session_token: str,
                                      cost: float):
        """更新用戶會話使用情況"""
        with self.db.session() as session:
            user_session = session.query(UserSession).filter_by(
                session_token=session_token
            ).first()
            
            if user_session:
                user_session.analysis_count += 1
                user_session.total_cost += cost
                user_session.budget_used += cost
                user_session.last_activity = datetime.utcnow()
                session.commit()
    
    async def check_user_budget(self, session_token: str) -> Tuple[bool, float]:
        """檢查用戶預算"""
        with self.db.session() as session:
            user_session = session.query(UserSession).filter_by(
                session_token=session_token,
                is_active=True
            ).first()
            
            if not user_session:
                return False, 0.0
            
            if user_session.expires_at < datetime.utcnow():
                user_session.is_active = False
                session.commit()
                return False, 0.0
            
            remaining_budget = user_session.budget_limit - user_session.budget_used
            return remaining_budget > 0, remaining_budget
    
    async def record_system_metrics(self,
                                  cpu_percent: float,
                                  memory_percent: float,
                                  disk_usage_percent: float,
                                  active_analyses: int,
                                  queue_size: int,
                                  cache_hit_rate: float,
                                  api_availability: float,
                                  average_response_time: float,
                                  error_rate: float):
        """記錄系統指標"""
        with self.db.session() as session:
            metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_usage_percent=disk_usage_percent,
                active_analyses=active_analyses,
                queue_size=queue_size,
                cache_hit_rate=cache_hit_rate,
                api_availability=api_availability,
                average_response_time=average_response_time,
                error_rate=error_rate
            )
            session.add(metrics)
            session.commit()
    
    async def record_error(self,
                         error_type: str,
                         error_message: str,
                         stack_trace: Optional[str] = None,
                         analysis_id: Optional[str] = None,
                         severity: str = 'error'):
        """記錄錯誤"""
        with self.db.session() as session:
            error_log = ErrorLog(
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace,
                analysis_id=analysis_id,
                severity=severity
            )
            session.add(error_log)
            session.commit()
    
    async def get_recent_analyses(self,
                                limit: int = 10,
                                analysis_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """獲取最近的分析記錄"""
        with self.db.session() as session:
            query = session.query(AnalysisRecord)
            
            if analysis_type:
                query = query.filter(AnalysisRecord.analysis_type == analysis_type)
            
            records = query.order_by(
                AnalysisRecord.created_at.desc()
            ).limit(limit).all()
            
            return [record.to_dict() for record in records]
    
    async def cleanup_old_records(self, days: int = 30):
        """清理舊記錄"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        with self.db.session() as session:
            # 清理分析記錄
            deleted_analyses = session.query(AnalysisRecord).filter(
                AnalysisRecord.created_at < cutoff_date
            ).delete()
            
            # 清理 API 日誌
            deleted_logs = session.query(ApiUsageLog).filter(
                ApiUsageLog.timestamp < cutoff_date
            ).delete()
            
            # 清理系統指標
            deleted_metrics = session.query(SystemMetrics).filter(
                SystemMetrics.timestamp < cutoff_date
            ).delete()
            
            # 清理過期會話
            deleted_sessions = session.query(UserSession).filter(
                or_(
                    UserSession.expires_at < datetime.utcnow(),
                    UserSession.last_activity < cutoff_date
                )
            ).delete()
            
            session.commit()
            
            logger.info(
                f"Cleaned up old records: {deleted_analyses} analyses, "
                f"{deleted_logs} logs, {deleted_metrics} metrics, "
                f"{deleted_sessions} sessions"
            )