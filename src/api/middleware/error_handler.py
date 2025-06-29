"""
錯誤處理中間件
"""
import traceback
import sys
from functools import wraps
from typing import Dict, Any, Optional, Tuple
from flask import jsonify, request
from werkzeug.exceptions import HTTPException

from ...core.exceptions import (
    AIAnalysisException,
    ProviderNotAvailableException,
    CancellationException,
    TokenLimitExceededException,
    FileSizeExceededException,
    BudgetExceededException,
    InvalidLogTypeException,
    CacheException,
    StorageException,
    ConfigurationException,
    AuthenticationException,
    RateLimitException,
    AnalysisTimeoutException,
    InvalidModeException
)
from ...storage.result_storage import ResultStorage
from ...utils.logger import get_logger

logger = get_logger(__name__)

class ErrorHandler:
    """錯誤處理器"""
    
    def __init__(self):
        self.storage = ResultStorage()
        self.error_mapping = self._init_error_mapping()
    
    def _init_error_mapping(self) -> Dict[type, Tuple[int, str]]:
        """初始化錯誤映射"""
        return {
            # 客戶端錯誤 (4xx)
            InvalidLogTypeException: (400, "Invalid log type"),
            InvalidModeException: (400, "Invalid analysis mode"),
            FileSizeExceededException: (400, "File size exceeds limit"),
            AuthenticationException: (401, "Authentication required"),
            BudgetExceededException: (402, "Budget exceeded"),
            ProviderNotAvailableException: (403, "AI provider not available"),
            RateLimitException: (429, "Rate limit exceeded"),
            
            # 伺服器錯誤 (5xx)
            ConfigurationException: (500, "Server configuration error"),
            StorageException: (500, "Storage error"),
            CacheException: (500, "Cache error"),
            TokenLimitExceededException: (500, "Token limit exceeded"),
            AnalysisTimeoutException: (504, "Analysis timeout"),
            
            # 特殊處理
            CancellationException: (200, "Analysis cancelled"),  # 取消不是錯誤
        }
    
    def handle_error(self, f):
        """錯誤處理裝飾器"""
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            try:
                return await f(*args, **kwargs)
            
            except HTTPException as e:
                # Werkzeug HTTP 異常
                return self._create_error_response(
                    e.code,
                    e.name,
                    e.description
                )
            
            except AIAnalysisException as e:
                # 自定義 AI 分析異常
                status_code, default_message = self.error_mapping.get(
                    type(e), (500, "AI analysis error")
                )
                
                # 特殊處理某些異常
                extra_data = {}
                if isinstance(e, RateLimitException) and e.retry_after:
                    extra_data['retry_after'] = e.retry_after
                elif isinstance(e, FileSizeExceededException):
                    extra_data['actual_size_mb'] = e.actual_mb
                    extra_data['limit_mb'] = e.limit_mb
                elif isinstance(e, BudgetExceededException):
                    extra_data['estimated_cost'] = e.estimated_cost
                    extra_data['budget'] = e.budget
                elif isinstance(e, TokenLimitExceededException):
                    extra_data['actual_tokens'] = e.actual
                    extra_data['limit_tokens'] = e.limit
                
                # 記錄錯誤
                await self._log_error(type(e).__name__, str(e), traceback.format_exc())
                
                return self._create_error_response(
                    status_code,
                    default_message,
                    str(e),
                    extra_data
                )
            
            except ValueError as e:
                # 值錯誤通常是客戶端問題
                return self._create_error_response(
                    400,
                    "Bad Request",
                    str(e)
                )
            
            except Exception as e:
                # 未預期的錯誤
                error_id = await self._log_error(
                    type(e).__name__,
                    str(e),
                    traceback.format_exc(),
                    severity='critical'
                )
                
                # 生產環境不要暴露詳細錯誤
                if self._is_production():
                    return self._create_error_response(
                        500,
                        "Internal Server Error",
                        "An unexpected error occurred",
                        {'error_id': error_id}
                    )
                else:
                    return self._create_error_response(
                        500,
                        "Internal Server Error",
                        str(e),
                        {
                            'error_id': error_id,
                            'traceback': traceback.format_exc().split('\n')
                        }
                    )
        
        return decorated_function
    
    def _create_error_response(self,
                             status_code: int,
                             error_type: str,
                             message: str,
                             extra_data: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], int]:
        """創建錯誤響應"""
        response = {
            'status': 'error',
            'error': {
                'type': error_type,
                'message': message,
                'code': status_code
            }
        }
        
        if extra_data:
            response['error'].update(extra_data)
        
        # 添加請求 ID（如果有）
        if hasattr(request, 'id'):
            response['request_id'] = request.id
        
        return jsonify(response), status_code
    
    async def _log_error(self,
                        error_type: str,
                        error_message: str,
                        stack_trace: Optional[str] = None,
                        severity: str = 'error') -> str:
        """記錄錯誤到資料庫"""
        try:
            # 獲取請求資訊
            request_data = {
                'method': request.method,
                'path': request.path,
                'remote_addr': request.remote_addr,
                'user_agent': request.headers.get('User-Agent'),
                'args': dict(request.args),
                'json': request.get_json(silent=True) if request.is_json else None
            }
            
            # 記錄到資料庫
            await self.storage.record_error(
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace,
                severity=severity,
                request_data=request_data
            )
            
            # 同時記錄到日誌
            logger.error(
                f"{error_type}: {error_message}",
                extra={
                    'stack_trace': stack_trace,
                    'request_data': request_data
                }
            )
            
            # 返回錯誤 ID
            return f"ERR-{request.id if hasattr(request, 'id') else 'UNKNOWN'}"
            
        except Exception as e:
            logger.error(f"Failed to log error: {e}")
            return "ERR-UNKNOWN"
    
    def _is_production(self) -> bool:
        """檢查是否為生產環境"""
        return os.getenv('ENVIRONMENT', 'development').lower() == 'production'
    
    def register_error_handlers(self, app):
        """註冊 Flask 錯誤處理器"""
        
        @app.errorhandler(404)
        def handle_404(e):
            return self._create_error_response(
                404,
                "Not Found",
                "The requested resource was not found"
            )
        
        @app.errorhandler(405)
        def handle_405(e):
            return self._create_error_response(
                405,
                "Method Not Allowed",
                f"The method {request.method} is not allowed for this endpoint"
            )
        
        @app.errorhandler(413)
        def handle_413(e):
            return self._create_error_response(
                413,
                "Payload Too Large",
                "The request payload is too large"
            )
        
        @app.errorhandler(500)
        def handle_500(e):
            error_id = asyncio.run(
                self._log_error(
                    "InternalServerError",
                    str(e),
                    traceback.format_exc(),
                    severity='critical'
                )
            )
            
            if self._is_production():
                return self._create_error_response(
                    500,
                    "Internal Server Error",
                    "An internal error occurred",
                    {'error_id': error_id}
                )
            else:
                return self._create_error_response(
                    500,
                    "Internal Server Error",
                    str(e),
                    {'error_id': error_id}
                )
        
        # 註冊自定義異常處理器
        for exception_class, (status_code, message) in self.error_mapping.items():
            @app.errorhandler(exception_class)
            def handle_custom_exception(e, status_code=status_code, message=message):
                return self._create_error_response(
                    status_code,
                    message,
                    str(e)
                )
    
    def format_validation_errors(self, errors: Dict[str, Any]) -> str:
        """格式化驗證錯誤"""
        messages = []
        for field, error in errors.items():
            if isinstance(error, list):
                messages.extend([f"{field}: {e}" for e in error])
            else:
                messages.append(f"{field}: {error}")
        return "; ".join(messages)

# 創建全局實例
error_handler = ErrorHandler()

# 導出便利函數
handle_errors = error_handler.handle_error