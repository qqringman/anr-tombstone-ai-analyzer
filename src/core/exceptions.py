"""
自定義異常類別
"""

class AIAnalysisException(Exception):
    """AI 分析基礎異常"""
    pass

class ProviderNotAvailableException(AIAnalysisException):
    """AI 提供者不可用異常"""
    pass

class CancellationException(AIAnalysisException):
    """分析取消異常"""
    def __init__(self, reason: str = "User cancelled"):
        self.reason = reason
        super().__init__(f"Analysis cancelled: {reason}")

class TokenLimitExceededException(AIAnalysisException):
    """Token 限制超過異常"""
    def __init__(self, actual: int, limit: int):
        self.actual = actual
        self.limit = limit
        super().__init__(f"Token limit exceeded: {actual} > {limit}")

class FileSizeExceededException(AIAnalysisException):
    """檔案大小超過異常"""
    def __init__(self, actual_mb: float, limit_mb: float):
        self.actual_mb = actual_mb
        self.limit_mb = limit_mb
        super().__init__(f"File size exceeded: {actual_mb:.1f}MB > {limit_mb:.1f}MB")

class BudgetExceededException(AIAnalysisException):
    """預算超過異常"""
    def __init__(self, estimated_cost: float, budget: float):
        self.estimated_cost = estimated_cost
        self.budget = budget
        super().__init__(f"Budget exceeded: ${estimated_cost:.2f} > ${budget:.2f}")

class InvalidLogTypeException(AIAnalysisException):
    """無效的日誌類型異常"""
    def __init__(self, log_type: str):
        self.log_type = log_type
        super().__init__(f"Invalid log type: {log_type}")

class CacheException(AIAnalysisException):
    """快取相關異常"""
    pass

class StorageException(AIAnalysisException):
    """儲存相關異常"""
    pass

class ConfigurationException(AIAnalysisException):
    """配置相關異常"""
    pass

class AuthenticationException(AIAnalysisException):
    """認證相關異常"""
    pass

class RateLimitException(AIAnalysisException):
    """速率限制異常"""
    def __init__(self, retry_after: int = None):
        self.retry_after = retry_after
        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after} seconds"
        super().__init__(message)

class AnalysisTimeoutException(AIAnalysisException):
    """分析超時異常"""
    def __init__(self, timeout_seconds: int):
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Analysis timeout after {timeout_seconds} seconds")

class InvalidModeException(AIAnalysisException):
    """無效的分析模式異常"""
    def __init__(self, mode: str):
        self.mode = mode
        super().__init__(f"Invalid analysis mode: {mode}")