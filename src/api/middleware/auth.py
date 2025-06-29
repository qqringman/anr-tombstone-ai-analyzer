"""
認證中間件
"""
import os
import jwt
import hashlib
from functools import wraps
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from flask import request, jsonify, g

from ...storage.result_storage import ResultStorage
from ...utils.logger import get_logger

logger = get_logger(__name__)

# 配置
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
API_TOKEN = os.getenv('API_TOKEN')
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

class AuthMiddleware:
    """認證中間件"""
    
    def __init__(self):
        self.storage = ResultStorage()
    
    def require_api_token(self, f):
        """需要 API Token 的裝飾器"""
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            # 檢查是否啟用了 API Token
            if not API_TOKEN:
                # 如果沒有設定 API Token，允許所有請求
                return await f(*args, **kwargs)
            
            # 從 header 獲取 token
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({
                    'status': 'error',
                    'message': 'Missing Authorization header'
                }), 401
            
            # 檢查 token 格式
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid Authorization header format'
                }), 401
            
            token = parts[1]
            
            # 驗證 token
            if token != API_TOKEN:
                logger.warning(f"Invalid API token attempt from {request.remote_addr}")
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid API token'
                }), 401
            
            return await f(*args, **kwargs)
        
        return decorated_function
    
    def require_jwt_token(self, f):
        """需要 JWT Token 的裝飾器"""
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            # 從 header 獲取 token
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({
                    'status': 'error',
                    'message': 'Missing Authorization header'
                }), 401
            
            # 檢查 token 格式
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid Authorization header format'
                }), 401
            
            token = parts[1]
            
            try:
                # 解碼 JWT
                payload = jwt.decode(
                    token,
                    JWT_SECRET_KEY,
                    algorithms=[JWT_ALGORITHM]
                )
                
                # 將用戶資訊存入 g
                g.user_id = payload.get('user_id')
                g.session_id = payload.get('session_id')
                
                return await f(*args, **kwargs)
                
            except jwt.ExpiredSignatureError:
                return jsonify({
                    'status': 'error',
                    'message': 'Token has expired'
                }), 401
            except jwt.InvalidTokenError as e:
                logger.warning(f"Invalid JWT token: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid token'
                }), 401
        
        return decorated_function
    
    def require_session(self, f):
        """需要有效會話的裝飾器"""
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            # 獲取 session token
            session_token = None
            
            # 優先從 header 獲取
            if 'X-Session-Token' in request.headers:
                session_token = request.headers['X-Session-Token']
            # 其次從 cookie 獲取
            elif 'session_token' in request.cookies:
                session_token = request.cookies.get('session_token')
            # 最後從查詢參數獲取
            elif 'session_token' in request.args:
                session_token = request.args.get('session_token')
            
            if not session_token:
                return jsonify({
                    'status': 'error',
                    'message': 'Missing session token'
                }), 401
            
            # 檢查會話是否有效
            # TODO: 實際檢查資料庫中的會話
            g.session_token = session_token
            
            return await f(*args, **kwargs)
        
        return decorated_function
    
    def check_budget(self, f):
        """檢查預算的裝飾器"""
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            # 需要先有會話
            if not hasattr(g, 'session_token'):
                return jsonify({
                    'status': 'error',
                    'message': 'Session required'
                }), 401
            
            # 檢查預算
            has_budget, remaining = await self.storage.check_user_budget(g.session_token)
            
            if not has_budget:
                return jsonify({
                    'status': 'error',
                    'message': 'Budget exceeded',
                    'remaining_budget': 0
                }), 402  # Payment Required
            
            g.remaining_budget = remaining
            
            return await f(*args, **kwargs)
        
        return decorated_function
    
    @staticmethod
    def generate_jwt_token(user_id: str, session_id: str) -> str:
        """生成 JWT token"""
        payload = {
            'user_id': user_id,
            'session_id': session_id,
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            'iat': datetime.utcnow()
        }
        
        return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    @staticmethod
    def generate_session_token() -> str:
        """生成會話 token"""
        # 使用時間戳和隨機數生成 token
        data = f"{datetime.utcnow().timestamp()}-{os.urandom(32).hex()}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def optional_auth(self, f):
        """可選的認證裝飾器（不強制要求）"""
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            # 嘗試獲取認證資訊，但不強制要求
            auth_header = request.headers.get('Authorization')
            if auth_header:
                parts = auth_header.split()
                if len(parts) == 2 and parts[0].lower() == 'bearer':
                    token = parts[1]
                    
                    # 嘗試作為 API token
                    if API_TOKEN and token == API_TOKEN:
                        g.auth_type = 'api_token'
                        g.authenticated = True
                    else:
                        # 嘗試作為 JWT
                        try:
                            payload = jwt.decode(
                                token,
                                JWT_SECRET_KEY,
                                algorithms=[JWT_ALGORITHM]
                            )
                            g.user_id = payload.get('user_id')
                            g.session_id = payload.get('session_id')
                            g.auth_type = 'jwt'
                            g.authenticated = True
                        except:
                            g.authenticated = False
                else:
                    g.authenticated = False
            else:
                g.authenticated = False
            
            return await f(*args, **kwargs)
        
        return decorated_function
    
    def require_admin(self, f):
        """需要管理員權限的裝飾器"""
        @wraps(f)
        async def decorated_function(*args, **kwargs):
            # 簡單實現：檢查特定的 admin token
            admin_token = os.getenv('ADMIN_TOKEN')
            if not admin_token:
                return jsonify({
                    'status': 'error',
                    'message': 'Admin access not configured'
                }), 403
            
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({
                    'status': 'error',
                    'message': 'Admin authorization required'
                }), 401
            
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid authorization format'
                }), 401
            
            if parts[1] != admin_token:
                logger.warning(f"Invalid admin access attempt from {request.remote_addr}")
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid admin credentials'
                }), 403
            
            g.is_admin = True
            return await f(*args, **kwargs)
        
        return decorated_function

# 創建全局實例
auth = AuthMiddleware()