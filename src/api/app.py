# src/api/app.py
"""
ANR/Tombstone AI 分析系統 - Flask 應用程式
"""

import os
import sys
from pathlib import Path
from flask_cors import CORS

# 將專案根目錄加入 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS
import json
import uuid
from datetime import datetime

# 添加這些導入 - 重要！
from src.config.base import AnalysisMode, ModelProvider
from src.core.exceptions import CancellationException
from src.core.cancellation import CancellationReason
from src.core.engine import CancellableAiAnalysisEngine

from asgiref.sync import async_to_sync

import asyncio
from asgiref.sync import async_to_sync
import threading

# 創建 Flask 應用
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

host = os.getenv('API_HOST', '0.0.0.0')
port = int(os.getenv('API_PORT', 5000))
host = 'localhost' if host == '0.0.0.0' else host
dynamic_origin = f"http://{host}:{port}"
CORS(app, resources={r"/api/*": {"origins": [dynamic_origin]}})

app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB

# 全局事件循環（用於異步操作）
async_loop = None
async_thread = None

def start_async_loop():
    """在單獨的線程中啟動異步事件循環"""
    global async_loop
    async_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(async_loop)
    async_loop.run_forever()

# 啟動異步線程
async_thread = threading.Thread(target=start_async_loop, daemon=True)
async_thread.start()

# 等待事件循環準備就緒
import time
time.sleep(0.1)

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
import concurrent.futures
import threading
import asyncio
import threading
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor

# 創建線程池
executor = ThreadPoolExecutor(max_workers=5)

@app.route('/api/ai/analyze-with-cancellation', methods=['POST'])
def analyze_with_cancellation():
    """可取消的 AI 分析 (SSE)"""
    data = request.get_json()
    
    content = data.get('content', '')
    log_type = data.get('log_type', 'anr')
    mode = data.get('mode', 'intelligent')
    provider = data.get('provider', 'anthropic')
    
    # 生成分析 ID
    analysis_id = str(uuid.uuid4())
    
    def generate():
        """生成 SSE 事件流"""
        import asyncio
        import threading
        from queue import Queue
        
        # 使用隊列來收集消息
        message_queue = Queue()
        error_occurred = threading.Event()
        
        def run_in_thread():
            """在新線程中運行異步代碼"""
            # 創建新的事件循環
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def async_analyze():
                try:
                    # 測試內容
                    message_queue.put("# 測試分析\n\n")
                    
                    # 獲取引擎
                    engine = app.config.get('ANALYSIS_ENGINE')
                    
                    if engine:
                        print(f"[DEBUG] Engine found, starting analysis")
                        
                        # 導入必要的類
                        try:
                            from src.config.base import AnalysisMode, ModelProvider
                            analysis_mode = AnalysisMode(mode)
                            model_provider = ModelProvider(provider) if provider else None
                        except Exception as e:
                            print(f"[DEBUG] Import error: {e}")
                            raise
                        
                        # 執行分析
                        print(f"[DEBUG] Calling engine.analyze_with_cancellation")
                        async for chunk in engine.analyze_with_cancellation(
                            content=content,
                            log_type=log_type,
                            mode=analysis_mode,
                            provider=model_provider,
                            analysis_id=analysis_id
                        ):
                            message_queue.put(chunk)
                    else:
                        print(f"[DEBUG] No engine, using direct API call")
                        # 直接 API 調用的邏輯
                        message_queue.put("## 直接 API 分析\n\n")
                        
                        # 這裡放你的 API 調用代碼
                        if provider == 'anthropic':
                            result = await call_anthropic_api(content, log_type, mode)
                            for chunk in result:
                                message_queue.put(chunk)
                        elif provider == 'openai':
                            result = await call_openai_api(content, log_type, mode)
                            for chunk in result:
                                message_queue.put(chunk)
                    
                    # 完成標記
                    message_queue.put(None)
                    
                except Exception as e:
                    print(f"[DEBUG] Error in async_analyze: {e}")
                    import traceback
                    traceback.print_exc()
                    error_occurred.set()
                    message_queue.put(f"ERROR: {str(e)}")
                    message_queue.put(None)
            
            # 運行異步函數
            loop.run_until_complete(async_analyze())
            loop.close()
        
        # 發送開始事件
        yield f"data: {json.dumps({'type': 'start', 'analysis_id': analysis_id})}\n\n"
        
        # 啟動線程
        thread = threading.Thread(target=run_in_thread)
        thread.start()
        
        # 從隊列讀取並生成 SSE 事件
        while True:
            try:
                chunk = message_queue.get(timeout=30)  # 30秒超時
                
                if chunk is None:
                    # 結束標記
                    break
                
                if chunk.startswith("ERROR:"):
                    # 錯誤消息
                    yield f"data: {json.dumps({'type': 'error', 'error': chunk[6:]})}\n\n"
                else:
                    # 正常內容
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
            
            except Exception as e:
                print(f"[DEBUG] Queue timeout or error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': 'Timeout'})}\n\n"
                break
        
        # 等待線程結束
        thread.join(timeout=5)
        
        # 發送完成事件
        if not error_occurred.is_set():
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
    
    # 輔助函數：調用 Anthropic API
    async def call_anthropic_api(content, log_type, mode):
        """異步調用 Anthropic API"""
        from anthropic import AsyncAnthropic
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            yield "Error: Anthropic API key not found"
            return
        
        client = AsyncAnthropic(api_key=api_key)
        
        model_map = {
            'quick': 'claude-3-haiku-20240307',
            'intelligent': 'claude-3-5-sonnet-20241022',
            'large_file': 'claude-3-5-sonnet-20241022',
            'max_token': 'claude-3-5-sonnet-20241022'
        }
        model = model_map.get(mode, 'claude-3-5-sonnet-20241022')
        
        prompt = _build_professional_prompt(content, log_type, mode)
        
        stream = await client.messages.create(
            model=model,
            max_tokens=4000 if mode == 'max_token' else 2000,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            stream=True
        )
        
        async for chunk in stream:
            if chunk.type == 'content_block_delta':
                text = chunk.delta.text
                if text:
                    yield text
    
    # 輔助函數：調用 OpenAI API
    async def call_openai_api(content, log_type, mode):
        """異步調用 OpenAI API"""
        from openai import AsyncOpenAI
        
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            yield "Error: OpenAI API key not found"
            return
        
        client = AsyncOpenAI(api_key=api_key)
        
        model_map = {
            'quick': 'gpt-3.5-turbo',
            'intelligent': 'gpt-4-turbo-preview',
            'large_file': 'gpt-4-turbo-preview',
            'max_token': 'gpt-4-turbo-preview'
        }
        model = model_map.get(mode, 'gpt-4-turbo-preview')
        
        messages = [
            {
                "role": "system",
                "content": _get_system_prompt(log_type)
            },
            {
                "role": "user",
                "content": _build_professional_prompt(content, log_type, mode)
            }
        ]
        
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            stream=True
        )
        
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    # 構建提示詞的輔助函數
    def _build_professional_prompt(content, log_type, mode):
        if log_type == 'anr':
            base_prompt = """你是一位資深的 Android 系統工程師，專門分析 ANR (Application Not Responding) 問題。
請分析以下 ANR 日誌，並提供詳細的技術分析報告。使用 Markdown 格式，包含程式碼範例。"""
        else:
            base_prompt = """你是一位資深的 Android Native 開發專家，專門分析 Tombstone (Native Crash) 問題。
請分析以下崩潰日誌，並提供詳細的技術分析報告。使用 Markdown 格式，包含程式碼範例。"""
        
        mode_prompts = {
            'quick': '\n\n請提供簡潔的分析（3-5個要點），重點解決問題。',
            'intelligent': '\n\n請提供全面的分析，包含問題診斷、解決方案和預防措施。',
            'large_file': '\n\n這是一個大型日誌文件，請進行深入分析，找出所有相關問題。',
            'max_token': '\n\n請提供最詳盡的分析，包含所有技術細節、多個解決方案、最佳實踐和案例。'
        }
        
        max_content_length = {
            'quick': 2000,
            'intelligent': 4000,
            'large_file': 8000,
            'max_token': 12000
        }.get(mode, 4000)
        
        truncated_content = content[:max_content_length]
        if len(content) > max_content_length:
            truncated_content += f"\n\n[註：日誌已截斷，原始長度 {len(content)} 字符]"
        
        return f"{base_prompt}{mode_prompts.get(mode, '')}\n\n日誌內容：\n```\n{truncated_content}\n```"
    
    def _get_system_prompt(log_type):
        if log_type == 'anr':
            return """You are an expert Android system engineer specializing in ANR analysis. 
You have deep knowledge of Android threading, Handler/Looper, and performance optimization.
Always respond in Traditional Chinese (繁體中文) with technical accuracy."""
        else:
            return """You are an expert Android Native developer specializing in crash analysis.
You have deep knowledge of C/C++, JNI, memory management, and debugging.
Always respond in Traditional Chinese (繁體中文) with technical accuracy."""
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )
    
# 取消分析
@app.route('/api/ai/cancel-analysis/<analysis_id>', methods=['POST'])
async def cancel_analysis(analysis_id):
    """取消分析"""
    engine = current_app.config.get('ANALYSIS_ENGINE')
    if not engine:
        return jsonify({
            'status': 'error',
            'message': 'Analysis engine not initialized'
        }), 503
    
    data = request.get_json() or {}
    reason = data.get('reason', 'user_cancelled')
    
    try:
        # 使用 CancellationReason 枚舉
        from src.core.cancellation import CancellationReason
        cancellation_reason = CancellationReason(reason)
    except ValueError:
        cancellation_reason = CancellationReason.USER_CANCELLED
    
    success = await engine.cancel_analysis(analysis_id, cancellation_reason)
    
    if success:
        return jsonify({
            'status': 'success',
            'message': f'Analysis {analysis_id} has been cancelled'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': f'Analysis {analysis_id} not found or already completed'
        }), 404

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
    
    # 初始化分析引擎
    from src.core.engine import CancellableAiAnalysisEngine
    import asyncio
    
    try:
        engine = CancellableAiAnalysisEngine()
        # 異步啟動引擎
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(engine.start())
        
        app.config['ANALYSIS_ENGINE'] = engine
        print("分析引擎初始化成功")
    except Exception as e:
        print(f"分析引擎初始化失敗: {e}")
        app.config['ANALYSIS_ENGINE'] = None

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