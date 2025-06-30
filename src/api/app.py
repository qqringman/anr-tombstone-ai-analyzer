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

# 創建 Flask 應用
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

host = os.getenv('API_HOST', '0.0.0.0')
port = int(os.getenv('API_PORT', 5000))
host = 'localhost' if host == '0.0.0.0' else host
dynamic_origin = f"http://{host}:{port}"
CORS(app, resources={r"/api/*": {"origins": [dynamic_origin]}})

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
    data = request.get_json()
    
    def generate():
        import time
        import os
        
        analysis_id = str(uuid.uuid4())
        yield f"data: {json.dumps({'type': 'start', 'analysis_id': analysis_id})}\n\n"
        
        content = data.get('content', '')
        log_type = data.get('log_type', 'anr')
        mode = data.get('mode', 'intelligent')
        provider = data.get('provider', 'anthropic')
        
        # Token 統計
        input_tokens = 0
        output_tokens = 0
        total_output = []
        
        try:
            if provider == 'anthropic':
                from anthropic import Anthropic
                
                api_key = os.getenv('ANTHROPIC_API_KEY')
                if not api_key:
                    raise Exception("Anthropic API key not found")
                
                client = Anthropic(api_key=api_key)
                
                # 根據模式選擇模型
                model_map = {
                    'quick': 'claude-3-haiku-20240307',
                    'intelligent': 'claude-3-5-sonnet-20241022',
                    'large_file': 'claude-3-5-sonnet-20241022',
                    'max_token': 'claude-3-5-sonnet-20241022'
                }
                model = model_map.get(mode, 'claude-3-5-sonnet-20241022')
                
                # 構建更專業的提示詞
                prompt = self._build_professional_prompt(content, log_type, mode)
                
                # 確認正在使用 API
                yield f"data: {json.dumps({'type': 'feedback', 'level': 'info', 'message': f'使用 Anthropic {model} 進行分析...'})}\n\n"
                
                print(f"[DEBUG] Calling Anthropic API with model: {model}")
                
                # 創建消息
                message = client.messages.create(
                    model=model,
                    max_tokens=4000 if mode == 'max_token' else 2000,
                    temperature=0.3,  # 降低溫度以獲得更一致的結果
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    stream=True
                )
                
                # 處理流式響應
                for chunk in message:
                    if chunk.type == 'message_start':
                        # 獲取輸入 token 數
                        if hasattr(chunk, 'message') and hasattr(chunk.message, 'usage'):
                            input_tokens = chunk.message.usage.input_tokens
                    
                    elif chunk.type == 'content_block_delta':
                        text = chunk.delta.text
                        if text:
                            total_output.append(text)
                            yield f"data: {json.dumps({'type': 'content', 'content': text})}\n\n"
                    
                    elif chunk.type == 'message_delta':
                        # 獲取輸出 token 數
                        if hasattr(chunk, 'usage'):
                            output_tokens = chunk.usage.output_tokens
                
                # 如果沒有從流中獲取 token 數，估算它們
                if input_tokens == 0:
                    input_tokens = self._estimate_tokens(prompt)
                if output_tokens == 0:
                    output_tokens = self._estimate_tokens(''.join(total_output))
                
            elif provider == 'openai':
                from openai import OpenAI
                
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    raise Exception("OpenAI API key not found")
                
                client = OpenAI(api_key=api_key)
                
                # 根據模式選擇模型
                model_map = {
                    'quick': 'gpt-3.5-turbo',
                    'intelligent': 'gpt-4-turbo-preview',
                    'large_file': 'gpt-4-turbo-preview',
                    'max_token': 'gpt-4-turbo-preview'
                }
                model = model_map.get(mode, 'gpt-4-turbo-preview')
                
                # 構建消息
                messages = [
                    {
                        "role": "system",
                        "content": self._get_system_prompt(log_type)
                    },
                    {
                        "role": "user",
                        "content": self._build_professional_prompt(content, log_type, mode)
                    }
                ]
                
                yield f"data: {json.dumps({'type': 'feedback', 'level': 'info', 'message': f'使用 OpenAI {model} 進行分析...'})}\n\n"
                
                # 調用 API
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.3,
                    stream=True
                )
                
                # 處理響應
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        total_output.append(text)
                        yield f"data: {json.dumps({'type': 'content', 'content': text})}\n\n"
                
                # 估算 tokens
                input_tokens = self._estimate_tokens(str(messages))
                output_tokens = self._estimate_tokens(''.join(total_output))
            
            # 發送 token 統計
            yield f"data: {json.dumps({'type': 'progress', 'progress': {'input_tokens': input_tokens, 'output_tokens': output_tokens, 'progress_percentage': 100}})}\n\n"
            
            # 計算成本
            cost = self._calculate_cost(input_tokens, output_tokens, provider, mode)
            yield f"data: {json.dumps({'type': 'feedback', 'level': 'info', 'message': f'分析完成！使用 {input_tokens} 輸入 tokens，{output_tokens} 輸出 tokens，預估成本：${cost:.4f}'})}\n\n"
            
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            
        except Exception as e:
            print(f"[DEBUG] API Error: {e}")
            import traceback
            traceback.print_exc()
            
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    def _build_professional_prompt(self, content, log_type, mode):
        """構建專業的提示詞"""
        if log_type == 'anr':
            base_prompt = """你是一位資深的 Android 系統工程師，專門分析 ANR (Application Not Responding) 問題。
請分析以下 ANR 日誌，並提供詳細的技術分析報告。使用 Markdown 格式，包含程式碼範例。

要求：
1. 使用繁體中文
2. 提供具體的程式碼範例
3. 包含技術細節和最佳實踐
4. 結構清晰，層次分明"""
        else:
            base_prompt = """你是一位資深的 Android Native 開發專家，專門分析 Tombstone (Native Crash) 問題。
請分析以下崩潰日誌，並提供詳細的技術分析報告。使用 Markdown 格式，包含程式碼範例。

要求：
1. 使用繁體中文
2. 提供 C/C++ 程式碼範例
3. 包含記憶體分析和調試建議
4. 結構清晰，層次分明"""
        
        # 根據模式調整分析深度
        if mode == 'quick':
            base_prompt += "\n\n請提供簡潔的分析（3-5個要點），重點解決問題。"
        elif mode == 'intelligent':
            base_prompt += "\n\n請提供全面的分析，包含問題診斷、解決方案和預防措施。"
        elif mode == 'large_file':
            base_prompt += "\n\n這是一個大型日誌文件，請進行深入分析，找出所有相關問題。"
        elif mode == 'max_token':
            base_prompt += "\n\n請提供最詳盡的分析，包含所有技術細節、多個解決方案、最佳實踐和案例。"
        
        # 添加日誌內容（限制長度）
        max_content_length = {
            'quick': 2000,
            'intelligent': 4000,
            'large_file': 8000,
            'max_token': 12000
        }.get(mode, 4000)
        
        truncated_content = content[:max_content_length]
        if len(content) > max_content_length:
            truncated_content += f"\n\n[註：日誌已截斷，原始長度 {len(content)} 字符]"
        
        return f"{base_prompt}\n\n日誌內容：\n```\n{truncated_content}\n```"
    
    def _get_system_prompt(self, log_type):
        """獲取系統提示詞"""
        if log_type == 'anr':
            return """You are an expert Android system engineer specializing in ANR analysis. 
You have deep knowledge of Android threading, Handler/Looper, and performance optimization.
Always respond in Traditional Chinese (繁體中文) with technical accuracy."""
        else:
            return """You are an expert Android Native developer specializing in crash analysis.
You have deep knowledge of C/C++, JNI, memory management, and debugging.
Always respond in Traditional Chinese (繁體中文) with technical accuracy."""
    
    def _estimate_tokens(self, text):
        """估算 token 數量"""
        # 粗略估算：平均每個 token 約 4 個字符
        return len(str(text)) // 4
    
    def _calculate_cost(self, input_tokens, output_tokens, provider, mode):
        """計算成本"""
        # 價格表（每 1K tokens）
        prices = {
            'anthropic': {
                'claude-3-haiku-20240307': {'input': 0.00025, 'output': 0.00125},
                'claude-3-5-sonnet-20241022': {'input': 0.003, 'output': 0.015}
            },
            'openai': {
                'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
                'gpt-4-turbo-preview': {'input': 0.01, 'output': 0.03}
            }
        }
        
        # 根據模式獲取模型
        if provider == 'anthropic':
            model = 'claude-3-haiku-20240307' if mode == 'quick' else 'claude-3-5-sonnet-20241022'
        else:
            model = 'gpt-3.5-turbo' if mode == 'quick' else 'gpt-4-turbo-preview'
        
        price = prices.get(provider, {}).get(model, {'input': 0.01, 'output': 0.03})
        
        input_cost = (input_tokens / 1000) * price['input']
        output_cost = (output_tokens / 1000) * price['output']
        
        return input_cost + output_cost
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

def analyze_with_cancellation_mock_impl(content, log_type, mode, provider):
    """Mock 實現用於測試"""

    def generate():
        """生成 SSE 事件流"""
        analysis_id = str(uuid.uuid4())
        
        # 開始事件
        yield f"data: {json.dumps({'type': 'start', 'analysis_id': analysis_id})}\n\n"
        
        # 模擬分析結果
        mock_content = """# {log_type.upper()} 分析報告

## 問題摘要

這是一個模擬的分析結果。在實際使用中，這裡會顯示：

1. **根本原因分析**
   - 主線程阻塞位置
   - 相關線程狀態
   - 資源競爭情況

2. **詳細解決方案**
   - 短期修復建議
   - 長期優化策略
   - 程式碼範例

3. **預防措施**
   - 監控建議
   - 最佳實踐

## 技術細節

根據日誌分析，主要問題出現在...

```java
// 範例程式碼
synchronized (lock) {
    // 避免在主線程執行耗時操作
}
```

## 結論

請根據以上分析進行相應的優化。
"""
        
        # 分段發送內容
        lines = mock_content.split('\n')
        total_lines = len(lines)
        
        for i, line in enumerate(lines):
            # 發送內容
            content_data = {'type': 'content', 'content': line + '\n'}
            yield f"data: {json.dumps(content_data)}\n\n"
            
            # 更新進度
            progress = ((i + 1) / total_lines) * 100
            progress_data = {
                'type': 'progress',
                'progress': {
                    'progress_percentage': progress,
                    'current_chunk': i + 1,
                    'total_chunks': total_lines,
                    'input_tokens': 1000 + i * 10,
                    'output_tokens': 500 + i * 5
                }
            }
            yield f"data: {json.dumps(progress_data)}\n\n"
            
            import time
            time.sleep(0.1)  # 模擬處理時間
        
        # 完成事件
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"
    
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