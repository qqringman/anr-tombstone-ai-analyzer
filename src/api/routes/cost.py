"""
成本相關路由
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import asyncio

from ...utils.cost_calculator import CostCalculator
from ...config.base import AnalysisMode, ModelProvider
from ..middleware.auth import auth
from ..middleware.rate_limit import rate_limit
from ..middleware.error_handler import handle_errors

# 創建藍圖
cost_bp = Blueprint('cost', __name__, url_prefix='/api/cost')

# 成本計算器實例
cost_calculator = CostCalculator()

# 估算分析成本
@cost_bp.route('/estimate', methods=['POST'])
@rate_limit(requests_per_minute=100)
def estimate_analysis_cost():
    """估算分析成本"""
    try:
        data = request.get_json()
        
        # 驗證必要參數
        file_size_kb = data.get('file_size_kb', 0)
        mode = data.get('mode', 'intelligent')
        provider = data.get('provider')
        budget = data.get('budget', 10.0)
        
        if file_size_kb <= 0:
            return jsonify({
                'status': 'error',
                'message': 'Invalid file size'
            }), 400
        
        # 轉換模式
        try:
            analysis_mode = AnalysisMode(mode)
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': f'Invalid analysis mode: {mode}'
            }), 400
        
        # 獲取成本比較
        comparisons = cost_calculator.compare_models_cost(
            file_size_kb, 
            analysis_mode, 
            budget
        )
        
        # 獲取推薦模型
        recommended_model = cost_calculator.recommend_model(
            file_size_kb,
            analysis_mode,
            budget
        )
        
        # 組織響應
        response_data = {
            'file_info': {
                'size_kb': file_size_kb,
                'estimated_tokens': int(file_size_kb * 400)  # 粗略估算
            },
            'cost_estimates': comparisons,
            'recommended_model': recommended_model,
            'recommended_mode': 'quick' if file_size_kb < 100 else 
                               'intelligent' if file_size_kb < 1000 else 
                               'large_file',
            'budget': {
                'limit': budget,
                'sufficient': any(c['is_within_budget'] for c in comparisons)
            }
        }
        
        # 如果指定了提供者，過濾結果
        if provider:
            response_data['cost_estimates'] = [
                c for c in comparisons 
                if c['provider'] == provider
            ]
        
        return jsonify({
            'status': 'success',
            'data': response_data
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 計算單個模型成本
@cost_bp.route('/calculate', methods=['POST'])
@rate_limit(requests_per_minute=200)
def calculate_model_cost():
    """計算特定模型的成本"""
    try:
        data = request.get_json()
        
        file_size_kb = data.get('file_size_kb', 0)
        model = data.get('model')
        budget = data.get('budget', 10.0)
        
        if not model:
            return jsonify({
                'status': 'error',
                'message': 'Model name is required'
            }), 400
        
        # 計算成本
        estimate = cost_calculator.calculate_cost(file_size_kb, model, budget)
        
        return jsonify({
            'status': 'success',
            'data': {
                'provider': estimate.provider,
                'model': estimate.model,
                'file_size_kb': estimate.file_size_kb,
                'estimated_input_tokens': estimate.estimated_input_tokens,
                'estimated_output_tokens': estimate.estimated_output_tokens,
                'input_cost': estimate.input_cost,
                'output_cost': estimate.output_cost,
                'total_cost': estimate.total_cost,
                'analysis_time_estimate': estimate.analysis_time_estimate,
                'is_within_budget': estimate.is_within_budget,
                'warnings': estimate.warnings
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

# 獲取成本統計
@cost_bp.route('/statistics', methods=['GET'])
@auth.optional_auth
async def get_cost_statistics():
    """獲取成本使用統計"""
    try:
        # 獲取參數
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        provider = request.args.get('provider')
        
        # 解析日期
        if start_date:
            start_date = datetime.fromisoformat(start_date)
        else:
            start_date = datetime.now() - timedelta(days=30)
        
        if end_date:
            end_date = datetime.fromisoformat(end_date)
        else:
            end_date = datetime.now()
        
        # 從引擎獲取統計
        from flask import current_app
        engine = current_app.config.get('ANALYSIS_ENGINE')
        
        if engine:
            stats = await engine.storage.get_cost_statistics(
                start_date, end_date, provider
            )
        else:
            # 模擬數據
            stats = {
                'total_cost': 0.0,
                'total_requests': 0,
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'by_provider': {},
                'daily_records': []
            }
        
        return jsonify({
            'status': 'success',
            'data': {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'summary': {
                    'total_cost': stats['total_cost'],
                    'total_requests': stats['total_requests'],
                    'total_tokens': stats['total_input_tokens'] + stats['total_output_tokens'],
                    'average_cost_per_request': (
                        stats['total_cost'] / stats['total_requests'] 
                        if stats['total_requests'] > 0 else 0
                    )
                },
                'by_provider': stats['by_provider'],
                'daily_breakdown': stats['daily_records']
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 獲取模型價格列表
@cost_bp.route('/models', methods=['GET'])
def get_model_prices():
    """獲取所有模型的價格資訊"""
    try:
        # 獲取所有模型資訊
        all_models = []
        
        for model_name, model_info in cost_calculator._model_info_cache.items():
            all_models.append({
                'provider': model_info.provider,
                'model': model_info.model,
                'tier': model_info.tier,
                'input_cost_per_1k': model_info.input_cost_per_1k,
                'output_cost_per_1k': model_info.output_cost_per_1k,
                'total_cost_per_1k': model_info.total_cost_per_1k,
                'context_window': model_info.context_window,
                'speed_rating': model_info.speed_rating,
                'quality_rating': model_info.quality_rating
            })
        
        # 按提供者分組
        by_provider = {}
        for model in all_models:
            provider = model['provider']
            if provider not in by_provider:
                by_provider[provider] = []
            by_provider[provider].append(model)
        
        # 按層級分組
        by_tier = {}
        for model in all_models:
            tier = model['tier']
            if tier not in by_tier:
                by_tier[tier] = []
            by_tier[tier].append(model)
        
        return jsonify({
            'status': 'success',
            'data': {
                'all_models': all_models,
                'by_provider': by_provider,
                'by_tier': by_tier,
                'total_models': len(all_models)
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 獲取層級模型
@cost_bp.route('/tier/<int:tier>', methods=['GET'])
def get_tier_models(tier: int):
    """獲取指定層級的模型"""
    try:
        if tier < 1 or tier > 4:
            return jsonify({
                'status': 'error',
                'message': 'Invalid tier. Must be between 1 and 4'
            }), 400
        
        models = cost_calculator.get_tier_models(tier)
        
        # 獲取每個模型的詳細資訊
        model_details = []
        for model_name in models:
            if model_name in cost_calculator._model_info_cache:
                info = cost_calculator._model_info_cache[model_name]
                model_details.append({
                    'model': model_name,
                    'provider': info.provider,
                    'input_cost_per_1k': info.input_cost_per_1k,
                    'output_cost_per_1k': info.output_cost_per_1k,
                    'speed_rating': info.speed_rating,
                    'quality_rating': info.quality_rating
                })
        
        return jsonify({
            'status': 'success',
            'data': {
                'tier': tier,
                'models': model_details,
                'count': len(model_details)
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 預算檢查
@cost_bp.route('/budget/check', methods=['POST'])
@auth.require_session
async def check_budget():
    """檢查用戶預算"""
    try:
        data = request.get_json()
        estimated_cost = data.get('estimated_cost', 0)
        
        # 從 session 獲取用戶資訊
        from flask import g
        session_token = g.get('session_token')
        
        if not session_token:
            return jsonify({
                'status': 'error',
                'message': 'Session required'
            }), 401
        
        # 檢查預算
        from flask import current_app
        engine = current_app.config.get('ANALYSIS_ENGINE')
        
        if engine:
            has_budget, remaining = await engine.storage.check_user_budget(session_token)
        else:
            # 模擬
            has_budget = True
            remaining = 10.0
        
        can_afford = remaining >= estimated_cost
        
        return jsonify({
            'status': 'success',
            'data': {
                'has_budget': has_budget,
                'remaining_budget': remaining,
                'estimated_cost': estimated_cost,
                'can_afford': can_afford,
                'message': 'Sufficient budget' if can_afford else 'Insufficient budget'
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 成本摘要格式化
@cost_bp.route('/format-summary', methods=['POST'])
def format_cost_summary():
    """格式化成本摘要"""
    try:
        data = request.get_json()
        
        file_size_kb = data.get('file_size_kb', 0)
        model = data.get('model')
        
        if not model:
            return jsonify({
                'status': 'error',
                'message': 'Model name is required'
            }), 400
        
        # 計算成本
        estimate = cost_calculator.calculate_cost(file_size_kb, model)
        
        # 格式化摘要
        summary = cost_calculator.format_cost_summary(estimate)
        
        return jsonify({
            'status': 'success',
            'data': {
                'summary': summary,
                'estimate': {
                    'total_cost': estimate.total_cost,
                    'analysis_time_estimate': estimate.analysis_time_estimate,
                    'is_within_budget': estimate.is_within_budget
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500