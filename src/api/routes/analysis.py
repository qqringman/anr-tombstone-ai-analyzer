from flask import Blueprint, request, jsonify, Response
import json
import uuid
from src.core.engine import CancellableAiAnalysisEngine

ai_bp = Blueprint('ai', __name__)
engine = CancellableAiAnalysisEngine()

@ai_bp.route('/analyze-with-cancellation', methods=['POST'])
async def analyze_with_cancellation():
    """可取消的 AI 分析 (SSE)"""
    data = request.json
    content = data.get('content')
    log_type = data.get('log_type')
    mode = AnalysisMode(data.get('mode', 'intelligent'))
    provider = ModelProvider(data.get('provider')) if data.get('provider') else None
    
    # 生成分析 ID
    analysis_id = str(uuid.uuid4())
    
    async def generate():
        try:
            # 發送開始事件
            yield f"data: {json.dumps({'type': 'start', 'analysis_id': analysis_id})}\n\n"
            
            # 執行分析
            async for chunk in engine.analyze_with_cancellation(
                content, log_type, mode, provider, analysis_id
            ):
                yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                
                # 定期發送進度
                status = engine.get_status()
                yield f"data: {json.dumps({'type': 'progress', 'progress': status['progress']})}\n\n"
            
            # 完成事件
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            
        except CancellationException:
            yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@ai_bp.route('/cancel-analysis/<analysis_id>', methods=['POST'])
def cancel_analysis(analysis_id: str):
    """取消分析"""
    data = request.json or {}
    reason = CancellationReason(data.get('reason', 'user_cancelled'))
    
    success = engine.cancel_analysis(analysis_id, reason)
    
    if success:
        return jsonify({
            'status': 'success',
            'message': f'分析 {analysis_id} 已取消'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': f'找不到分析 {analysis_id}'
        }), 404