"""
結構化日誌系統
"""
import logging
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from logging.handlers import RotatingFileHandler
import traceback

class StructuredFormatter(logging.Formatter):
    """結構化日誌格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日誌記錄為 JSON"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 添加額外的上下文資訊
        if hasattr(record, 'context'):
            log_data['context'] = record.context
        
        # 添加異常資訊
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data, ensure_ascii=False)

class StructuredLogger:
    """結構化日誌記錄器"""
    
    def __init__(self, name: str, log_dir: str = "logs", 
                 level: str = "INFO", max_bytes: int = 10485760, 
                 backup_count: int = 5):
        """
        初始化日誌記錄器
        
        Args:
            name: 日誌記錄器名稱
            log_dir: 日誌目錄
            level: 日誌級別
            max_bytes: 單個日誌檔案最大大小（位元組）
            backup_count: 保留的備份檔案數量
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # 確保日誌目錄存在
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        
        # 檔案處理器（JSON 格式）
        file_handler = RotatingFileHandler(
            Path(log_dir) / f"{name}.json",
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(file_handler)
        
        # 控制台處理器（人類可讀格式）
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 防止日誌傳播到父記錄器
        self.logger.propagate = False
    
    def _log_with_context(self, level: str, message: str, **context):
        """帶上下文的日誌記錄"""
        extra = {'context': context} if context else {}
        getattr(self.logger, level)(message, extra=extra)
    
    def debug(self, message: str, **context):
        """DEBUG 級別日誌"""
        self._log_with_context('debug', message, **context)
    
    def info(self, message: str, **context):
        """INFO 級別日誌"""
        self._log_with_context('info', message, **context)
    
    def warning(self, message: str, **context):
        """WARNING 級別日誌"""
        self._log_with_context('warning', message, **context)
    
    def error(self, message: str, exception: Optional[Exception] = None, **context):
        """ERROR 級別日誌"""
        if exception:
            self.logger.error(message, exc_info=exception, extra={'context': context})
        else:
            self._log_with_context('error', message, **context)
    
    def critical(self, message: str, **context):
        """CRITICAL 級別日誌"""
        self._log_with_context('critical', message, **context)
    
    def log_analysis(self, level: str, message: str, **kwargs):
        """記錄分析相關日誌"""
        context = {
            'type': 'analysis',
            **kwargs
        }
        self._log_with_context(level, message, **context)
    
    def log_api_request(self, method: str, url: str, status_code: Optional[int] = None, 
                       duration: Optional[float] = None, **kwargs):
        """記錄 API 請求"""
        context = {
            'type': 'api_request',
            'method': method,
            'url': url,
            'status_code': status_code,
            'duration': duration,
            **kwargs
        }
        level = 'info' if status_code and 200 <= status_code < 400 else 'error'
        self._log_with_context(level, f"API {method} {url}", **context)
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """記錄性能指標"""
        context = {
            'type': 'performance',
            'operation': operation,
            'duration': duration,
            **kwargs
        }
        self._log_with_context('info', f"Performance: {operation}", **context)
    
    def log_cost(self, provider: str, model: str, input_tokens: int, 
                 output_tokens: int, cost: float, **kwargs):
        """記錄成本資訊"""
        context = {
            'type': 'cost',
            'provider': provider,
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost': cost,
            **kwargs
        }
        self._log_with_context('info', f"Cost tracking: ${cost:.4f}", **context)
    
    def log_cancellation(self, analysis_id: str, reason: str, **kwargs):
        """記錄取消操作"""
        context = {
            'type': 'cancellation',
            'analysis_id': analysis_id,
            'reason': reason,
            **kwargs
        }
        self._log_with_context('warning', f"Analysis cancelled: {analysis_id}", **context)

# 全局日誌記錄器快取
_loggers: Dict[str, StructuredLogger] = {}

def get_logger(name: str, **kwargs) -> StructuredLogger:
    """獲取或創建日誌記錄器"""
    if name not in _loggers:
        _loggers[name] = StructuredLogger(name, **kwargs)
    return _loggers[name]

# 預設日誌記錄器
default_logger = get_logger("ai_analyzer")