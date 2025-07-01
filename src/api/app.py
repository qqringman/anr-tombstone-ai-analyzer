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
        # 發送開始事件
        yield f"data: {json.dumps({'type': 'start', 'analysis_id': analysis_id})}\n\n"
        
        try:
            # 獲取 engine
            engine = app.config.get('ANALYSIS_ENGINE')
            if not engine:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Engine not initialized'})}\n\n"
                return
            
            # 轉換參數
            from src.config.base import AnalysisMode, ModelProvider
            try:
                analysis_mode = AnalysisMode(mode)
            except ValueError:
                analysis_mode = AnalysisMode.INTELLIGENT
            
            try:
                model_provider = ModelProvider(provider) if provider else None
            except ValueError:
                model_provider = None
            
            # 設置 provider
            if model_provider:
                engine.set_provider(model_provider)
            
            # 創建取消令牌
            from src.core.cancellation import CancellationToken
            token = CancellationToken(analysis_id)
            
            # 獲取 wrapper
            wrapper = engine._wrappers.get(engine._current_provider)
            if not wrapper:
                yield f"data: {json.dumps({'type': 'error', 'error': 'No wrapper available'})}\n\n"
                return
            
            # 選擇分析器
            if log_type.lower() == 'anr':
                analyzer = wrapper._anr_analyzer
            else:
                analyzer = wrapper._tombstone_analyzer
            
            # 初始化統計
            chunk_count = 0
            total_content = []
            input_tokens = 0
            output_tokens = 0
            
            # 估算輸入 tokens
            input_tokens = wrapper.config.estimate_tokens(content)
            
            # 立即發送初始進度
            progress_data = {
                'progress_percentage': 0,
                'current_chunk': 0,
                'total_chunks': 1,  # 預估
                'input_tokens': input_tokens,
                'output_tokens': 0
            }
            yield f"data: {json.dumps({'type': 'progress', 'progress': progress_data})}\n\n"
            
            # 執行分析
            async def run_analysis():
                nonlocal chunk_count, input_tokens, output_tokens
                
                # 初始化時間追蹤變數
                last_progress_time = time.time()
                
                # 使用 analyzer 分析
                async for chunk in analyzer.analyze(content, analysis_mode, token):
                    total_content.append(chunk)
                    chunk_count += 1
                    
                    # 估算輸出 tokens (累積)
                    current_output = ''.join(total_content)
                    output_tokens = wrapper.config.estimate_tokens(current_output)
                    
                    # 計算進度
                    estimated_progress = min(chunk_count * 5, 90)  # 最多到 90%
                    
                    # 發送內容
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                    
                    # 獲取當前時間
                    current_time = time.time()
                    
                    # 每 5 個 chunk 或每 500ms 更新一次進度
                    if chunk_count % 5 == 0 or (current_time - last_progress_time) > 0.5:
                        progress_data = {
                            'progress_percentage': estimated_progress,
                            'current_chunk': chunk_count,
                            'total_chunks': chunk_count + 10,  # 動態估算
                            'input_tokens': input_tokens,
                            'output_tokens': output_tokens
                        }
                        yield f"data: {json.dumps({'type': 'progress', 'progress': progress_data})}\n\n"
                        last_progress_time = current_time
                
                # 最終統計
                total_text = ''.join(total_content)
                final_output_tokens = wrapper.config.estimate_tokens(total_text)
                
                # 計算成本
                model = wrapper.config.get_model_for_mode(analysis_mode)
                cost = wrapper.calculate_cost(input_tokens, final_output_tokens, model)
                
                # 發送最終進度
                final_progress = {
                    'progress_percentage': 100,
                    'current_chunk': chunk_count,
                    'total_chunks': chunk_count,
                    'input_tokens': input_tokens,
                    'output_tokens': final_output_tokens,
                    'total_cost': cost
                }
                yield f"data: {json.dumps({'type': 'progress', 'progress': final_progress})}\n\n"
                
                # 更新資料庫（如果有整合）
                if hasattr(engine, 'storage'):
                    try:
                        await engine.storage.update_analysis_result(
                            analysis_id,
                            total_text,
                            input_tokens,
                            final_output_tokens,
                            cost,
                            "completed"
                        )
                    except:
                        pass
                
                # 發送完成事件
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            
            # 使用 asyncio 運行分析
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # 轉換異步生成器為同步
                async_gen = run_analysis()
                while True:
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            async_gen.__anext__(),
                            async_loop
                        )
                        result = future.result(timeout=30)  # 30秒超時
                        yield result
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'type': 'error', 'error': 'Analysis timeout'})}\n\n"
                        break
                        
            except Exception as e:
                import traceback
                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
            finally:
                loop.close()
                
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
    
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
    engine = app.config.get('ANALYSIS_ENGINE')
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