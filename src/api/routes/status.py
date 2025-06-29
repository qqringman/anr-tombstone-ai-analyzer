"""
狀態相關路由
"""
from flask import Blueprint, jsonify, request, Response
import json
import asyncio
from datetime import datetime

from ...core.engine import CancellableAiAnalysisEngine
from ...utils.status_manager import EnhancedStatusManager
from ..middleware.auth import auth
from ..middleware.rate_limit import rate_limit
from ..middleware.error_handler import handle_errors
from ..utils.sse import create_sse_response, SSEStream

# 創建藍圖
status_bp = Blueprint('status', __name__, url_prefix='/api/status')

# 獲取引擎實例（應該從應用上下文獲取）
def get_engine() -> CancellableAiAnalysisEngine:
    """獲取分析引擎實例"""
    from flask import current_app
    return current_app.config.get('ANALYSIS_ENGINE')

# 獲取當前狀態
@status_bp.route('/current', methods=['GET'])
@rate_limit(requests_per_minute=120)
def get_current_status():
    """獲取當前系統狀態"""
    engine = get_engine()
    
    if not engine:
        return jsonify({
            'status': 'error',
            'message': 'Analysis engine not initialized'
        }), 500
    
    try:
        status = engine.get_status()
        
        return jsonify({
            'status': 'success',
            'data': {
                'system_status': status.get('status', 'unknown'),
                'current_provider': status.get('current_provider'),
                'available_providers': status.get('available_providers', []),
                'active_analyses': engine.get_active_analyses(),
                'queue_status': status.get('queue_status', {}),
                'api_usage': status.get('api_usage', {}),
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 獲取分析狀態
@status_bp.route('/analysis/<analysis_id>', methods=['GET'])
@rate_limit(requests_per_minute=300)
async def get_analysis_status(analysis_id: str):
    """獲取特定分析的狀態"""
    engine = get_engine()
    
    try:
        # 從資料庫獲取分析記錄
        record = await engine.storage.get_analysis_record(analysis_id)
        
        if not record:
            return jsonify({
                'status': 'error',
                'message': 'Analysis not found'
            }), 404
        
        # 檢查是否為活動分析
        active_analyses = engine.get_active_analyses()
        is_active = any(a['id'] == analysis_id for a in active_analyses)
        
        return jsonify({
            'status': 'success',
            'data': {
                'analysis_id': analysis_id,
                'status': record['status'],
                'log_type': record['analysis_type'],
                'mode': record['analysis_mode'],
                'provider': record['provider'],
                'is_active': is_active,
                'created_at': record['created_at'],
                'completed_at': record['completed_at'],
                'duration_seconds': record['duration_seconds'],
                'error_message': record['error_message'],
                'progress': {
                    'input_tokens': record['input_tokens'],
                    'output_tokens': record['output_tokens'],
                    'total_cost': record['total_cost']
                }
            }
        })
    except Exception as e:
        return handle_errors(lambda: None)(e)

# 即時狀態流 (SSE)
@status_bp.route('/stream', methods=['GET'])
@auth.optional_auth
def stream_status():
    """串流即時狀態更新"""
    def generate():
        stream = SSEStream()
        engine = get_engine()
        
        # 初始狀態
        status = engine.get_status()
        yield stream.send_message({
            'type': 'initial',
            'status': status
        })
        
        # 狀態更新回調
        def status_callback(new_status):
            return stream.send_message({
                'type': 'update',
                'status': new_status,
                'timestamp': datetime.now().isoformat()
            })
        
        # 註冊監聽器
        engine.add_status_listener(status_callback)
        
        try:
            # 定期發送心跳
            while True:
                yield stream.send_heartbeat()
                import time
                time.sleep(30)  # 30秒心跳
        except GeneratorExit:
            # 清理監聽器
            engine.status_manager.remove_listener(status_callback)
    
    return create_sse_response(generate())

# 獲取活動分析列表
@status_bp.route('/active-analyses', methods=['GET'])
@rate_limit(requests_per_minute=60)
def get_active_analyses():
    """獲取所有活動中的分析"""
    engine = get_engine()
    
    try:
        active = engine.get_active_analyses()
        
        return jsonify({
            'status': 'success',
            'data': {
                'count': len(active),
                'analyses': active,
                'cancellation_stats': engine.get_cancellation_stats()
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 獲取佇列狀態
@status_bp.route('/queue', methods=['GET'])
@rate_limit(requests_per_minute=60)
def get_queue_status():
    """獲取任務佇列狀態"""
    engine = get_engine()
    
    try:
        queue_status = engine.task_queue.get_queue_status()
        
        # 獲取待處理和執行中的任務
        pending_tasks = engine.task_queue.get_pending_tasks()
        running_tasks = engine.task_queue.get_running_tasks()
        
        return jsonify({
            'status': 'success',
            'data': {
                'queue_size': queue_status['queue_size'],
                'running_tasks': queue_status['running_tasks'],
                'total_tasks': queue_status['total_tasks'],
                'status_counts': queue_status['status_counts'],
                'stats': queue_status['stats'],
                'is_full': queue_status['is_full'],
                'pending_tasks': [
                    {
                        'id': task.id,
                        'log_type': task.log_type,
                        'mode': task.mode.value,
                        'priority': task.priority,
                        'created_at': task.created_at.isoformat()
                    }
                    for task in pending_tasks[:10]  # 最多返回10個
                ],
                'running_tasks': [
                    {
                        'id': task.id,
                        'log_type': task.log_type,
                        'mode': task.mode.value,
                        'started_at': task.started_at.isoformat() if task.started_at else None
                    }
                    for task in running_tasks
                ]
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 獲取系統指標
@status_bp.route('/metrics', methods=['GET'])
@auth.require_api_token
async def get_system_metrics():
    """獲取系統性能指標"""
    engine = get_engine()
    
    try:
        # 獲取快取統計
        cache_stats = engine.cache_manager.get_stats()
        
        # 獲取 API 統計
        api_stats = {}
        for provider, wrapper in engine._wrappers.items():
            api_stats[provider.value] = wrapper.get_api_stats()
        
        # 獲取健康狀態
        health_status = await engine.get_health_status()
        
        return jsonify({
            'status': 'success',
            'data': {
                'cache': cache_stats,
                'api_usage': api_stats,
                'health': health_status['metrics'],
                'active_analyses': len(engine.get_active_analyses()),
                'queue_metrics': engine.task_queue.get_queue_status()['stats'],
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 清理已完成的任務
@status_bp.route('/cleanup', methods=['POST'])
@auth.require_api_token
async def cleanup_completed():
    """清理已完成的任務和分析"""
    engine = get_engine()
    
    try:
        # 獲取參數
        data = request.get_json() or {}
        older_than_hours = data.get('older_than_hours', 24)
        
        # 清理任務佇列
        queue_cleaned = engine.task_queue.clear_completed_tasks(older_than_hours)
        
        # 清理取消令牌
        await engine.cleanup_completed_analyses(older_than_hours)
        
        # 清理資料庫記錄
        await engine.storage.cleanup_old_records(older_than_hours // 24)
        
        return jsonify({
            'status': 'success',
            'data': {
                'queue_tasks_cleaned': queue_cleaned,
                'message': f'Cleaned up tasks older than {older_than_hours} hours'
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 獲取狀態歷史
@status_bp.route('/history', methods=['GET'])
@auth.optional_auth
async def get_status_history():
    """獲取狀態歷史記錄"""
    try:
        # 獲取參數
        hours = request.args.get('hours', 24, type=int)
        
        # 從資料庫獲取系統指標歷史
        # 這需要 storage 模組支援
        # metrics = await engine.storage.get_system_metrics_history(hours)
        
        return jsonify({
            'status': 'success',
            'data': {
                'message': 'Status history endpoint - implementation pending',
                'requested_hours': hours
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500