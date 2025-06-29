# src/api/app.py
"""
ANR/Tombstone AI 分析系統 - Flask 應用程式
"""

import os
import sys
from pathlib import Path

# 將專案根目錄加入 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
import json
import uuid
from datetime import datetime

# 創建 Flask 應用
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB

# ===== 路由定義 =====

# 根路徑 - 提供 API 資訊
@app.route('/')
def index():
    """API 首頁"""
    return jsonify({
        "service": "ANR/Tombstone AI Analyzer API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/api/health",
            "analyze": "/api/ai/analyze-with-ai",
            "analyze_cancellable": "/api/ai/analyze-with-cancellation",
            "estimate_cost": "/api/ai/estimate-analysis-cost",
            "api_docs": "/api/docs"
        },
        "web_ui": "Please access the web interface through http://localhost (port 80)",
        "documentation": "https://github.com/your-org/anr-analyzer"
    })

# 健康檢查
@app.route('/api/health')
def health():
    """健康檢查端點"""
    return jsonify({
        "status": "healthy",
        "service": "ANR/Tombstone AI Analyzer",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "checks": {
            "api": "ok",
            "database": check_database(),
            "redis": check_redis(),
            "ai_providers": check_ai_providers()
        }
    })

# 詳細健康檢查
@app.route('/api/health/detailed')
def health_detailed():
    """詳細健康檢查"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": os.getenv('ENVIRONMENT', 'development'),
        "python_version": sys.version,
        "components": {
            "flask": {
                "status": "ok",
                "version": "3.0.0"
            },
            "database": {
                "status": check_database(),
                "url": "postgresql://***"
            },
            "redis": {
                "status": check_redis(),
                "url": "redis://***"
            },
            "anthropic": {
                "status": "ok" if os.getenv('ANTHROPIC_API_KEY') else "missing_key",
                "has_key": bool(os.getenv('ANTHROPIC_API_KEY'))
            },
            "openai": {
                "status": "ok" if os.getenv('OPENAI_API_KEY') else "missing_key",
                "has_key": bool(os.getenv('OPENAI_API_KEY'))
            }
        }
    })

# 分析 API (基本版本)
@app.route('/api/ai/analyze-with-ai', methods=['POST'])
def analyze_basic():
    """基本分析 API（同步）"""
    try:
        data = request.get_json()
        
        # 驗證必要參數
        required = ['content', 'log_type']
        missing = [field for field in required if field not in data]
        if missing:
            return jsonify({
                "status": "error",
                "message": f"Missing required fields: {', '.join(missing)}"
            }), 400
        
        # 模擬分析（實際實作需要連接真實的分析引擎）
        result = {
            "status": "success",
            "data": {
                "analysis_id": str(uuid.uuid4()),
                "log_type": data['log_type'],
                "mode": data.get('mode', 'intelligent'),
                "result": f"這是 {data['log_type']} 的分析結果（模擬）\n\n1. 問題摘要\n2. 詳細分析\n3. 建議解決方案",
                "tokens_used": {
                    "input": 1000,
                    "output": 500
                },
                "cost": 0.15,
                "duration": 2.5
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# 可取消的分析 API (SSE)
@app.route('/api/ai/analyze-with-cancellation', methods=['POST'])
def analyze_with_cancellation():
    """可取消的分析 API（Server-Sent Events）"""
    data = request.get_json()
    
    def generate():
        """生成 SSE 事件流"""
        analysis_id = str(uuid.uuid4())
        
        # 開始事件
        yield f"data: {json.dumps({'type': 'start', 'analysis_id': analysis_id})}\n\n"
        
        # 模擬分析過程
        for i in range(10):
            # 進度更新
            progress = (i + 1) * 10
            yield f"data: {json.dumps({'type': 'progress', 'progress': {'progress_percentage': progress}})}\n\n"
            
            # 內容片段
            yield f"data: {json.dumps({'type': 'content', 'content': f'分析進度 {progress}%...'})}\n\n"
            
            import time
            time.sleep(0.5)  # 模擬處理時間
        
        # 完成事件
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

# 取消分析
@app.route('/api/ai/cancel-analysis/<analysis_id>', methods=['POST'])
def cancel_analysis(analysis_id):
    """取消分析"""
    return jsonify({
        "status": "success",
        "message": f"Analysis {analysis_id} cancelled"
    })

# 成本估算
@app.route('/api/ai/estimate-analysis-cost', methods=['POST'])
def estimate_cost():
    """估算分析成本"""
    data = request.get_json()
    file_size_kb = data.get('file_size_kb', 0)
    mode = data.get('mode', 'intelligent')
    
    # 簡單的成本計算邏輯
    base_cost = {
        'quick': 0.1,
        'intelligent': 0.5,
        'large_file': 1.0,
        'max_token': 2.0
    }
    
    cost_per_mb = base_cost.get(mode, 0.5)
    total_cost = (file_size_kb / 1024) * cost_per_mb
    
    return jsonify({
        "status": "success",
        "data": {
            "file_info": {
                "size_kb": file_size_kb,
                "estimated_tokens": int(file_size_kb * 400)  # 假設 1KB ≈ 400 tokens
            },
            "cost_estimates": [
                {
                    "provider": "anthropic",
                    "model": "claude-sonnet-4",
                    "total_cost": round(total_cost, 2),
                    "analysis_time_minutes": round(file_size_kb / 200, 1)  # 假設 200KB/分鐘
                }
            ],
            "recommended_mode": "quick" if file_size_kb < 1024 else "intelligent"
        }
    })

# 檢查檔案大小
@app.route('/api/ai/check-file-size', methods=['POST'])
def check_file_size():
    """檢查檔案大小"""
    data = request.get_json()
    file_size = data.get('file_size', 0)
    
    max_size = 20 * 1024 * 1024  # 20MB
    
    return jsonify({
        "status": "success",
        "data": {
            "file_size": file_size,
            "max_size": max_size,
            "is_valid": file_size <= max_size,
            "message": "File size is acceptable" if file_size <= max_size else "File too large"
        }
    })

# API 文檔
@app.route('/api/docs')
def api_docs():
    """API 文檔"""
    return jsonify({
        "title": "ANR/Tombstone AI Analyzer API",
        "version": "1.0.0",
        "description": "AI-powered Android crash log analysis",
        "endpoints": [
            {
                "path": "/api/health",
                "method": "GET",
                "description": "Health check endpoint"
            },
            {
                "path": "/api/ai/analyze-with-ai",
                "method": "POST",
                "description": "Analyze log file (synchronous)",
                "parameters": {
                    "content": "string (required) - Log content",
                    "log_type": "string (required) - 'anr' or 'tombstone'",
                    "mode": "string (optional) - Analysis mode",
                    "provider": "string (optional) - AI provider"
                }
            },
            {
                "path": "/api/ai/analyze-with-cancellation",
                "method": "POST",
                "description": "Analyze log file with cancellation support (SSE)",
                "parameters": "Same as analyze-with-ai"
            },
            {
                "path": "/api/ai/cancel-analysis/{analysis_id}",
                "method": "POST",
                "description": "Cancel ongoing analysis"
            },
            {
                "path": "/api/ai/estimate-analysis-cost",
                "method": "POST",
                "description": "Estimate analysis cost",
                "parameters": {
                    "file_size_kb": "number (required) - File size in KB",
                    "mode": "string (optional) - Analysis mode"
                }
            }
        ]
    })

# 測試用：提供靜態檔案（開發模式）
if os.getenv('ENVIRONMENT') == 'development':
    @app.route('/web/<path:path>')
    def serve_static(path):
        """開發模式下提供靜態檔案"""
        web_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'web')
        return send_from_directory(web_dir, path)
    
    @app.route('/web/')
    def serve_index():
        """開發模式下提供首頁"""
        web_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'web')
        return send_from_directory(web_dir, 'index.html')

# ===== 輔助函數 =====

def check_database():
    """檢查資料庫連接"""
    # TODO: 實作真實的資料庫檢查
    return "ok" if os.getenv('DATABASE_URL') else "not_configured"

def check_redis():
    """檢查 Redis 連接"""
    # TODO: 實作真實的 Redis 檢查
    return "ok" if os.getenv('REDIS_URL') else "not_configured"

def check_ai_providers():
    """檢查 AI 提供者"""
    providers = []
    if os.getenv('ANTHROPIC_API_KEY'):
        providers.append('anthropic')
    if os.getenv('OPENAI_API_KEY'):
        providers.append('openai')
    return providers if providers else ['none']

# ===== 錯誤處理 =====

@app.errorhandler(404)
def not_found(error):
    """404 錯誤處理"""
    return jsonify({
        "status": "error",
        "message": "Endpoint not found",
        "code": 404,
        "help": "Visit / for API information or /api/docs for documentation"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """500 錯誤處理"""
    return jsonify({
        "status": "error",
        "message": "Internal server error",
        "code": 500
    }), 500

# ===== 啟動應用 =====

if __name__ == '__main__':
    # 載入環境變數
    from dotenv import load_dotenv
    load_dotenv()
    
    # 取得配置
    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', 5000))
    debug = os.getenv('ENVIRONMENT') == 'development'
    
    print(f"""
    ==========================================
    ANR/Tombstone AI Analyzer API Server
    ==========================================
    
    API Server: http://{host}:{port}
    Health Check: http://{host}:{port}/api/health
    API Docs: http://{host}:{port}/api/docs
    
    Web UI: Please use Nginx (port 80) or visit http://{host}:{port}/web/ in development mode
    
    Environment: {os.getenv('ENVIRONMENT', 'development')}
    ==========================================
    """)
    
    # 啟動服務器
    app.run(host=host, port=port, debug=debug)