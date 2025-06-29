"""
速率限制中間件
"""
import time
import json
from functools import wraps
from typing import Dict, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta
from flask import request, jsonify, g
import redis
import asyncio

from ...config.system_config import get_system_config
from ...utils.logger import get_logger

logger = get_logger(__name__)

class RateLimiter:
    """速率限制器"""
    
    def __init__(self, 
                 requests_per_minute: int = 60,
                 requests_per_hour: int = 1000,
                 burst_size: int = 10,
                 use_redis: bool = True):
        """
        初始化速率限制器
        
        Args:
            requests_per_minute: 每分鐘請求數限制
            requests_per_hour: 每小時請求數限制
            burst_size: 突發請求數
            use_redis: 是否使用 Redis（用於分散式環境）
        """
        config = get_system_config()
        self.requests_per_minute = requests_per_minute or config.rate_limits.requests_per_minute
        self.requests_per_hour = requests_per_hour or config.rate_limits.requests_per_hour
        self.burst_size = burst_size or config.rate_limits.burst_size
        
        # Redis 連接
        self.use_redis = use_redis and self._init_redis()
        
        # 本地儲存（當 Redis 不可用時使用）
        self.local_storage = defaultdict(lambda: {
            'minute_tokens': self.requests_per_minute,
            'hour_tokens': self.requests_per_hour,
            'last_minute_reset': time.time(),
            'last_hour_reset': time.time()
        })
    
    def _init_redis(self) -> bool:
        """初始化 Redis 連接"""
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("Redis rate limiter initialized")
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to Redis, using local rate limiting: {e}")
            self.redis_client = None
            return False
    
    def _get_client_id(self) -> str:
        """獲取客戶端標識"""
        # 優先使用認證的用戶 ID
        if hasattr(g, 'user_id') and g.user_id:
            return f"user:{g.user_id}"
        
        # 使用會話 token
        if hasattr(g, 'session_token') and g.session_token:
            return f"session:{g.session_token}"
        
        # 使用 IP 地址
        return f"ip:{request.remote_addr}"
    
    async def check_rate_limit(self, client_id: str) -> Tuple[bool, Dict[str, int]]:
        """
        檢查速率限制
        
        Returns:
            (是否允許, 剩餘配額資訊)
        """
        if self.use_redis:
            return await self._check_redis_rate_limit(client_id)
        else:
            return self._check_local_rate_limit(client_id)
    
    async def _check_redis_rate_limit(self, client_id: str) -> Tuple[bool, Dict[str, int]]:
        """使用 Redis 檢查速率限制"""
        now = time.time()
        minute_key = f"rate_limit:minute:{client_id}"
        hour_key = f"rate_limit:hour:{client_id}"
        
        pipe = self.redis_client.pipeline()
        
        # 使用滑動窗口算法
        # 分鐘級限制
        minute_window_start = now - 60
        pipe.zremrangebyscore(minute_key, 0, minute_window_start)
        pipe.zcard(minute_key)
        
        # 小時級限制
        hour_window_start = now - 3600
        pipe.zremrangebyscore(hour_key, 0, hour_window_start)
        pipe.zcard(hour_key)
        
        results = pipe.execute()
        minute_count = results[1]
        hour_count = results[3]
        
        # 檢查是否超過限制
        if minute_count >= self.requests_per_minute or hour_count >= self.requests_per_hour:
            return False, {
                'minute_remaining': max(0, self.requests_per_minute - minute_count),
                'hour_remaining': max(0, self.requests_per_hour - hour_count),
                'minute_reset': int(now + 60),
                'hour_reset': int(now + 3600)
            }
        
        # 記錄這次請求
        pipe = self.redis_client.pipeline()
        pipe.zadd(minute_key, {str(now): now})
        pipe.expire(minute_key, 60)
        pipe.zadd(hour_key, {str(now): now})
        pipe.expire(hour_key, 3600)
        pipe.execute()
        
        return True, {
            'minute_remaining': self.requests_per_minute - minute_count - 1,
            'hour_remaining': self.requests_per_hour - hour_count - 1,
            'minute_reset': int(now + 60),
            'hour_reset': int(now + 3600)
        }
    
    def _check_local_rate_limit(self, client_id: str) -> Tuple[bool, Dict[str, int]]:
        """使用本地儲存檢查速率限制"""
        now = time.time()
        client_data = self.local_storage[client_id]
        
        # 重置分鐘級 token
        if now - client_data['last_minute_reset'] >= 60:
            client_data['minute_tokens'] = self.requests_per_minute
            client_data['last_minute_reset'] = now
        
        # 重置小時級 token
        if now - client_data['last_hour_reset'] >= 3600:
            client_data['hour_tokens'] = self.requests_per_hour
            client_data['last_hour_reset'] = now
        
        # 檢查是否有足夠的 token
        if client_data['minute_tokens'] <= 0 or client_data['hour_tokens'] <= 0:
            return False, {
                'minute_remaining': client_data['minute_tokens'],
                'hour_remaining': client_data['hour_tokens'],
                'minute_reset': int(client_data['last_minute_reset'] + 60),
                'hour_reset': int(client_data['last_hour_reset'] + 3600)
            }
        
        # 消耗 token
        client_data['minute_tokens'] -= 1
        client_data['hour_tokens'] -= 1
        
        return True, {
            'minute_remaining': client_data['minute_tokens'],
            'hour_remaining': client_data['hour_tokens'],
            'minute_reset': int(client_data['last_minute_reset'] + 60),
            'hour_reset': int(client_data['last_hour_reset'] + 3600)
        }
    
    def rate_limit(self, 
                   requests_per_minute: Optional[int] = None,
                   requests_per_hour: Optional[int] = None):
        """速率限制裝飾器"""
        def decorator(f):
            @wraps(f)
            async def decorated_function(*args, **kwargs):
                # 檢查是否啟用速率限制
                if os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'false':
                    return await f(*args, **kwargs)
                
                client_id = self._get_client_id()
                
                # 使用自定義限制或預設限制
                limiter = self
                if requests_per_minute or requests_per_hour:
                    limiter = RateLimiter(
                        requests_per_minute or self.requests_per_minute,
                        requests_per_hour or self.requests_per_hour,
                        self.burst_size,
                        self.use_redis
                    )
                
                # 檢查速率限制
                allowed, quota_info = await limiter.check_rate_limit(client_id)
                
                # 設置響應頭
                response_headers = {
                    'X-RateLimit-Limit-Minute': str(limiter.requests_per_minute),
                    'X-RateLimit-Limit-Hour': str(limiter.requests_per_hour),
                    'X-RateLimit-Remaining-Minute': str(quota_info['minute_remaining']),
                    'X-RateLimit-Remaining-Hour': str(quota_info['hour_remaining']),
                    'X-RateLimit-Reset-Minute': str(quota_info['minute_reset']),
                    'X-RateLimit-Reset-Hour': str(quota_info['hour_reset'])
                }
                
                if not allowed:
                    # 計算重試時間
                    retry_after = min(
                        quota_info['minute_reset'] - int(time.time()),
                        quota_info['hour_reset'] - int(time.time())
                    )
                    
                    response = jsonify({
                        'status': 'error',
                        'message': 'Rate limit exceeded',
                        'retry_after': retry_after,
                        'quota': quota_info
                    })
                    response.status_code = 429
                    response.headers['Retry-After'] = str(retry_after)
                    
                    # 添加速率限制頭
                    for header, value in response_headers.items():
                        response.headers[header] = value
                    
                    logger.warning(f"Rate limit exceeded for {client_id}")
                    return response
                
                # 執行原函數
                result = await f(*args, **kwargs)
                
                # 如果是 Response 對象，添加頭
                if hasattr(result, 'headers'):
                    for header, value in response_headers.items():
                        result.headers[header] = value
                
                return result
            
            # 保持同步函數的兼容性
            if not asyncio.iscoroutinefunction(f):
                @wraps(f)
                def sync_decorated_function(*args, **kwargs):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        return loop.run_until_complete(
                            decorated_function(*args, **kwargs)
                        )
                    finally:
                        loop.close()
                
                return sync_decorated_function
            
            return decorated_function
        
        return decorator
    
    def get_usage_stats(self, client_id: Optional[str] = None) -> Dict[str, Any]:
        """獲取使用統計"""
        if not client_id:
            client_id = self._get_client_id()
        
        if self.use_redis:
            # 從 Redis 獲取統計
            minute_key = f"rate_limit:minute:{client_id}"
            hour_key = f"rate_limit:hour:{client_id}"
            
            now = time.time()
            minute_count = self.redis_client.zcount(minute_key, now - 60, now)
            hour_count = self.redis_client.zcount(hour_key, now - 3600, now)
            
            return {
                'client_id': client_id,
                'minute_usage': minute_count,
                'hour_usage': hour_count,
                'minute_limit': self.requests_per_minute,
                'hour_limit': self.requests_per_hour
            }
        else:
            # 從本地儲存獲取
            if client_id in self.local_storage:
                data = self.local_storage[client_id]
                return {
                    'client_id': client_id,
                    'minute_usage': self.requests_per_minute - data['minute_tokens'],
                    'hour_usage': self.requests_per_hour - data['hour_tokens'],
                    'minute_limit': self.requests_per_minute,
                    'hour_limit': self.requests_per_hour
                }
            else:
                return {
                    'client_id': client_id,
                    'minute_usage': 0,
                    'hour_usage': 0,
                    'minute_limit': self.requests_per_minute,
                    'hour_limit': self.requests_per_hour
                }
    
    def reset_client_limit(self, client_id: str):
        """重置客戶端限制"""
        if self.use_redis:
            minute_key = f"rate_limit:minute:{client_id}"
            hour_key = f"rate_limit:hour:{client_id}"
            self.redis_client.delete(minute_key, hour_key)
        else:
            if client_id in self.local_storage:
                del self.local_storage[client_id]
        
        logger.info(f"Reset rate limit for {client_id}")

# 創建全局實例
rate_limiter = RateLimiter()

# 導出便利函數
rate_limit = rate_limiter.rate_limit