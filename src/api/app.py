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

from src.config.rate_limits import get_rate_limits_manager, RateLimitTier

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
            from src.utils.cost_calculator import CostCalculator
            
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
            
            # 創建並註冊取消令牌
            from src.core.cancellation import CancellationToken
            token = CancellationToken(analysis_id)
            
            # 重要：將 token 註冊到管理器
            if hasattr(engine, 'cancellation_manager'):
                engine.cancellation_manager._tokens[analysis_id] = token
            elif hasattr(engine, '_active_analyses'):
                engine._active_analyses[analysis_id] = token
            
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
            
            # 初始化成本計算器
            cost_calculator = CostCalculator()
            
            # 計算檔案大小（KB）
            file_size_kb = len(content.encode('utf-8')) / 1024
            
            # 獲取模型配置
            model = wrapper.config.get_model_for_mode(analysis_mode)
            model_config = wrapper.config.get_model_config(model)
            
            # 使用統一的 token 估算方法
            estimated_input_tokens, estimated_output_tokens = cost_calculator.estimate_tokens(
                file_size_kb, 
                model_provider or ModelProvider.ANTHROPIC
            )
            
            # 如果 wrapper 有更準確的估算方法，使用它
            if hasattr(wrapper.config, 'estimate_tokens'):
                actual_input_tokens = wrapper.config.estimate_tokens(content)
            else:
                actual_input_tokens = estimated_input_tokens
            
            # 計算初始成本（只有輸入）
            initial_input_cost = (actual_input_tokens / 1000.0) * model_config.input_cost_per_1k
            
            # 立即發送初始進度
            progress_data = {
                'progress_percentage': 0,
                'current_chunk': 0,
                'total_chunks': 1,
                'input_tokens': actual_input_tokens,
                'output_tokens': 0,
                'total_cost': initial_input_cost,
                'cost_breakdown': {
                    'input_cost': initial_input_cost,
                    'output_cost': 0,
                    'model': model,
                    'provider': wrapper.provider.value,
                    'input_price_per_1k': model_config.input_cost_per_1k,
                    'output_price_per_1k': model_config.output_cost_per_1k
                }
            }
            yield f"data: {json.dumps({'type': 'progress', 'progress': progress_data})}\n\n"
            
            # 執行分析
            chunk_count = 0
            total_content = []
            accumulated_output = ""
            last_progress_time = time.time()
            
            async def run_analysis():
                nonlocal chunk_count, accumulated_output, last_progress_time
                
                try:
                    # 使用 analyzer 分析
                    async for chunk in analyzer.analyze(content, analysis_mode, token):
                        # 檢查是否已取消
                        if token.is_cancelled:
                            yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
                            return
                            
                        total_content.append(chunk)
                        accumulated_output += chunk
                        chunk_count += 1
                        
                        # 發送內容
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                        
                        # 獲取當前時間
                        current_time = time.time()
                        
                        # 每 3 個 chunk 或每 500ms 更新一次進度
                        if chunk_count % 3 == 0 or (current_time - last_progress_time) > 0.5:
                            # 計算當前輸出 tokens
                            if hasattr(wrapper.config, 'estimate_tokens'):
                                current_output_tokens = wrapper.config.estimate_tokens(accumulated_output)
                            else:
                                # 使用 cost_calculator 的估算
                                output_size_kb = len(accumulated_output.encode('utf-8')) / 1024
                                _, current_output_tokens = cost_calculator.estimate_tokens(
                                    output_size_kb, 
                                    model_provider or ModelProvider.ANTHROPIC
                                )
                            
                            # 計算當前成本
                            current_input_cost = (actual_input_tokens / 1000.0) * model_config.input_cost_per_1k
                            current_output_cost = (current_output_tokens / 1000.0) * model_config.output_cost_per_1k
                            current_total_cost = current_input_cost + current_output_cost

                            # 確保成本在合理範圍內
                            if current_total_cost > 1000:  # 如果成本超過 $1000，可能有錯誤
                                print(f"Warning: Unusually high cost detected: ${current_total_cost}")
                                print(f"Input tokens: {actual_input_tokens}, Output tokens: {current_output_tokens}")
                                print(f"Input price: ${model_config.input_cost_per_1k}/1k, Output price: ${model_config.output_cost_per_1k}/1k")
                                                            
                            # 計算進度百分比
                            # 基於輸出 tokens 相對於預期輸出的比例
                            progress_percentage = min(
                                (current_output_tokens / max(estimated_output_tokens, 1)) * 100, 
                                90
                            )
                            
                            # 更新進度數據
                            progress_data = {
                                'progress_percentage': progress_percentage,
                                'current_chunk': chunk_count,
                                'total_chunks': max(chunk_count + 5, 10),
                                'input_tokens': actual_input_tokens,
                                'output_tokens': current_output_tokens,
                                'total_cost': current_total_cost,
                                'cost_breakdown': {
                                    'input_cost': current_input_cost,
                                    'output_cost': current_output_cost,
                                    'model': model,
                                    'provider': wrapper.provider.value,
                                    'input_price_per_1k': model_config.input_cost_per_1k,
                                    'output_price_per_1k': model_config.output_cost_per_1k
                                }
                            }
                            yield f"data: {json.dumps({'type': 'progress', 'progress': progress_data})}\n\n"
                            last_progress_time = current_time
                    
                except Exception as e:
                    if "CancellationException" in str(type(e).__name__):
                        yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
                        return
                    else:
                        raise
                
                # 分析完成，計算最終統計
                final_output = ''.join(total_content)
                
                # 計算最終的 tokens
                if hasattr(wrapper.config, 'estimate_tokens'):
                    final_output_tokens = wrapper.config.estimate_tokens(final_output)
                else:
                    output_size_kb = len(final_output.encode('utf-8')) / 1024
                    _, final_output_tokens = cost_calculator.estimate_tokens(
                        output_size_kb, 
                        model_provider or ModelProvider.ANTHROPIC
                    )
                
                # 計算最終成本
                final_input_cost = (actual_input_tokens / 1000.0) * model_config.input_cost_per_1k
                final_output_cost = (final_output_tokens / 1000.0) * model_config.output_cost_per_1k
                final_total_cost = final_input_cost + final_output_cost
                
                # 發送最終進度（100%）
                final_progress = {
                    'progress_percentage': 100,
                    'current_chunk': chunk_count,
                    'total_chunks': chunk_count,
                    'input_tokens': actual_input_tokens,
                    'output_tokens': final_output_tokens,
                    'total_cost': final_total_cost,
                    'cost_breakdown': {
                        'input_cost': final_input_cost,
                        'output_cost': final_output_cost,
                        'total': final_total_cost,
                        'model': model,
                        'provider': wrapper.provider.value,
                        'input_price_per_1k': model_config.input_cost_per_1k,
                        'output_price_per_1k': model_config.output_cost_per_1k
                    },
                    'summary': {
                        'total_tokens': actual_input_tokens + final_output_tokens,
                        'chunks_processed': chunk_count,
                        'content_length': len(final_output)
                    }
                }
                yield f"data: {json.dumps({'type': 'progress', 'progress': final_progress})}\n\n"
                
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
                        # 檢查取消狀態
                        if token.is_cancelled:
                            yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
                            break
                            
                        future = asyncio.run_coroutine_threadsafe(
                            async_gen.__anext__(),
                            async_loop
                        )
                        result = future.result(timeout=30)
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
                # 清理
                if hasattr(engine, 'cancellation_manager'):
                    engine.cancellation_manager._tokens.pop(analysis_id, None)
                elif hasattr(engine, '_active_analyses'):
                    engine._active_analyses.pop(analysis_id, None)
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
        # 如果有取消管理器，使用它
        if hasattr(engine, 'cancellation_manager'):
            from src.core.cancellation import CancellationReason
            try:
                cancellation_reason = CancellationReason(reason)
            except ValueError:
                cancellation_reason = CancellationReason.USER_CANCELLED
            
            success = await engine.cancellation_manager.cancel(analysis_id, cancellation_reason)
        else:
            # 簡單的取消實作
            success = True
            print(f"[DEBUG] Cancelling analysis {analysis_id}")
        
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
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 成本估算
@app.route('/api/ai/estimate-analysis-cost', methods=['POST'])
def estimate_cost():
    """估算分析成本"""
    try:
        data = request.get_json()
        file_size_kb = data.get('file_size_kb', 0)
        mode = data.get('mode', 'intelligent')
        provider = data.get('provider', 'anthropic')
        
        # 使用 CostCalculator 進行統一計算
        from src.utils.cost_calculator import CostCalculator
        from src.config.base import AnalysisMode, ModelProvider
        
        calculator = CostCalculator()
        
        # 轉換參數
        try:
            analysis_mode = AnalysisMode(mode)
            model_provider = ModelProvider(provider)
        except ValueError:
            analysis_mode = AnalysisMode.INTELLIGENT
            model_provider = ModelProvider.ANTHROPIC
        
        # 獲取該模式下的模型
        if model_provider == ModelProvider.ANTHROPIC:
            from src.config.anthropic_config import AnthropicApiConfig
            config = AnthropicApiConfig()
        else:
            from src.config.openai_config import OpenApiConfig
            config = OpenApiConfig()
        
        model = config.get_model_for_mode(analysis_mode)
        model_config = config.get_model_config(model)
        
        # 計算成本
        estimate = calculator.calculate_cost(file_size_kb, model)
        
        # 單獨計算分塊資訊
        input_tokens = estimate.estimated_input_tokens
        context_window = model_config.context_window
        effective_context = int(context_window * 0.7)  # 保留 30% buffer
        
        # 計算需要多少個 chunks
        chunks_needed = max(1, (input_tokens + effective_context - 1) // effective_context)
        
        # 計算 rate limit 影響（如果函數存在）
        rate_limit_info = None
        try:
            rate_limit_info = calculate_rate_limited_time(file_size_kb, model, provider)
        except:
            pass
        
        response_data = {
            "status": "success",
            "data": {
                "file_info": {
                    "size_kb": file_size_kb,
                    "estimated_tokens": estimate.estimated_input_tokens + estimate.estimated_output_tokens,
                    "input_tokens": estimate.estimated_input_tokens,
                    "output_tokens": estimate.estimated_output_tokens
                },
                "cost_estimates": [{
                    "provider": estimate.provider,
                    "model": estimate.model,
                    "total_cost": round(estimate.total_cost, 4),  # 限制小數位數
                    "input_cost": round(estimate.input_cost, 4),
                    "output_cost": round(estimate.output_cost, 4),
                    "analysis_time_minutes": estimate.analysis_time_estimate,
                    "api_queries_needed": chunks_needed,
                    "chunks_to_process": chunks_needed,
                    "warnings": estimate.warnings
                }],
                "analysis_plan": {
                    "total_chunks": chunks_needed,
                    "tokens_per_chunk": effective_context,
                    "estimated_api_calls": chunks_needed,
                    "parallel_possible": chunks_needed > 1
                },
                "recommended_mode": "quick" if file_size_kb < 100 else 
                                   "intelligent" if file_size_kb < 1000 else 
                                   "large_file"
            }
        }
        
        # 如果有 rate limit 資訊，添加進去
        if rate_limit_info:
            response_data["data"]["rate_limit_details"] = rate_limit_info.get('rate_limit_info', {})
        
        return jsonify(response_data)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def calculate_api_queries(file_size_kb, model, calculator):
    """計算需要的 API 查詢次數"""
    model_info = calculator._model_info_cache.get(model)
    if not model_info:
        return 1
    
    provider = ModelProvider(model_info.provider)
    input_tokens, _ = calculator.estimate_tokens(file_size_kb, provider)
    
    # 計算有效的 context window (預留 20% 給 prompt 和輸出)
    effective_context = int(model_info.context_window * 0.8)
    
    # 計算需要的查詢次數
    queries = max(1, (input_tokens + effective_context - 1) // effective_context)
    
    return queries

@app.route('/api/ai/rate-limits/<provider>', methods=['GET'])
def get_rate_limits(provider):
    """獲取指定提供者的速率限制資訊"""
    try:
        rate_limits_manager = get_rate_limits_manager()
        
        # 獲取參數
        tier = request.args.get('tier')
        model = request.args.get('model')
        
        if tier:
            try:
                tier = RateLimitTier(tier)
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': f'Invalid tier: {tier}'
                }), 400
        
        # 獲取 provider 實例
        provider_instance = rate_limits_manager.get_provider(provider)
        
        # 獲取限制
        limits = provider_instance.get_limits(tier, model)
        
        return jsonify({
            'status': 'success',
            'data': {
                'provider': provider,
                'tier': tier.value if tier else rate_limits_manager.get_current_tier(provider),
                'model': model,
                'limits': {
                    'requests_per_minute': limits.requests_per_minute,
                    'tokens_per_minute': limits.tokens_per_minute,
                    'requests_per_day': limits.requests_per_day,
                    'tokens_per_day': limits.tokens_per_day,
                    'concurrent_requests': limits.concurrent_requests
                },
                'formatted': provider_instance.format_info(tier, model),
                'available_tiers': [t.value for t in provider_instance.get_available_tiers()]
            }
        })
        
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/ai/suggest-tier', methods=['POST'])
def suggest_tier():
    """建議最適合的速率層級"""
    try:
        data = request.get_json()
        file_size_kb = data.get('file_size_kb', 0)
        provider = data.get('provider', 'anthropic')
        desired_time = data.get('desired_time_minutes', 10)
        
        rate_limits_manager = get_rate_limits_manager()
        
        suggestion = rate_limits_manager.suggest_optimal_settings(
            provider, file_size_kb, desired_time
        )
        
        return jsonify({
            'status': 'success',
            'data': suggestion
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
        
# 計算基於 rate limit 的時間估算
def calculate_rate_limited_time(file_size_kb, model, provider):
    """計算考慮 rate limits 的時間估算"""
    calculator = CostCalculator()
    rate_limits_manager = get_rate_limits_manager()
    
    # 估算 tokens
    provider_enum = ModelProvider(provider)
    input_tokens, output_tokens = calculator.estimate_tokens(file_size_kb, provider_enum)
    total_tokens = input_tokens + output_tokens
    
    # 計算查詢次數
    queries_needed = calculate_api_queries(file_size_kb, model, calculator)
    
    # 獲取時間估算
    time_estimate = rate_limits_manager.calculate_time_estimate(
        provider, total_tokens, queries_needed, model=model
    )
    
    # 獲取當前限制
    current_limits = rate_limits_manager.get_limits(provider, model=model)
    
    return {
        'queries_needed': queries_needed,
        'total_tokens': total_tokens,
        'rate_limit_info': time_estimate,
        'current_limits': {
            'requests_per_minute': current_limits.requests_per_minute,
            'tokens_per_minute': current_limits.tokens_per_minute,
            'tier': rate_limits_manager.get_current_tier(provider)
        }
    }

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