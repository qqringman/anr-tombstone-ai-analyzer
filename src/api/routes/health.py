"""
健康檢查相關路由
"""
from flask import Blueprint, jsonify, request
import os
import psutil
from datetime import datetime
import asyncio

from ...utils.health_checker import HealthChecker, HealthStatus
from ..middleware.rate_limit import rate_limit
from ..middleware.error_handler import handle_errors

# 創建藍圖
health_bp = Blueprint('health', __name__, url_prefix='/api/health')

# 基本健康檢查
@health_bp.route('', methods=['GET'])
@health_bp.route('/', methods=['GET'])
def health_check():
    """基本健康檢查端點"""
    try:
        # 獲取引擎
        from flask import current_app
        engine = current_app.config.get('ANALYSIS_ENGINE')
        
        if not engine:
            return jsonify({
                'status': 'unhealthy',
                'service': 'ANR/Tombstone AI Analyzer',
                'timestamp': datetime.now().isoformat(),
                'message': 'Engine not initialized'
            }), 503
        
        # 執行健康檢查
        health_status = asyncio.run(engine.get_health_status())
        
        # 簡化的響應
        overall_status = health_status['overall']['status']
        http_status = 200 if overall_status == 'healthy' else 503
        
        return jsonify({
            'status': overall_status,
            'service': 'ANR/Tombstone AI Analyzer',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
            'checks': {
                component['name']: component['status']
                for component in health_status['components'].values()
            }
        }), http_status
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'service': 'ANR/Tombstone AI Analyzer',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 503

# 詳細健康檢查
@health_bp.route('/detailed', methods=['GET'])
@rate_limit(requests_per_minute=30)
async def health_check_detailed():
    """詳細健康檢查"""
    try:
        from flask import current_app
        engine = current_app.config.get('ANALYSIS_ENGINE')
        
        # 系統資訊
        system_info = {
            'python_version': os.sys.version,
            'platform': os.sys.platform,
            'cpu_count': psutil.cpu_count(),
            'memory_total_gb': round(psutil.virtual_memory().total / (1024**3), 2),
            'disk_total_gb': round(psutil.disk_usage('/').total / (1024**3), 2)
        }
        
        # 環境資訊
        environment = {
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'debug_mode': current_app.debug,
            'api_host': os.getenv('API_HOST', '0.0.0.0'),
            'api_port': os.getenv('API_PORT', '5000')
        }
        
        if engine:
            # 獲取詳細健康狀態
            health_status = await engine.get_health_status()
            
            # 獲取可用性統計
            availability = engine.health_checker.get_availability(24)  # 24小時
            
            # 組件狀態
            components = {}
            for name, component in health_status['components'].items():
                components[name] = {
                    'status': component['status'],
                    'message': component['message'],
                    'details': component.get('details', {}),
                    'last_check': component['last_check']
                }
            
            return jsonify({
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'overall': health_status['overall'],
                'system': system_info,
                'environment': environment,
                'components': components,
                'metrics': health_status.get('metrics', {}),
                'availability': {
                    '24h': round(availability, 2),
                    'status': 'good' if availability > 99 else 'degraded' if availability > 95 else 'poor'
                }
            })
        else:
            return jsonify({
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'message': 'Engine not initialized',
                'system': system_info,
                'environment': environment
            }), 503
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 組件健康檢查
@health_bp.route('/component/<component_name>', methods=['GET'])
@rate_limit(requests_per_minute=60)
async def check_component_health(component_name: str):
    """檢查特定組件的健康狀態"""
    try:
        from flask import current_app
        engine = current_app.config.get('ANALYSIS_ENGINE')
        
        if not engine:
            return jsonify({
                'status': 'error',
                'message': 'Engine not initialized'
            }), 503
        
        # 獲取健康狀態
        health_status = await engine.get_health_status()
        
        # 查找組件
        component = health_status['components'].get(component_name)
        
        if not component:
            return jsonify({
                'status': 'error',
                'message': f'Component {component_name} not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'data': {
                'component': component_name,
                'health': component,
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 活躍性檢查 (Liveness)
@health_bp.route('/live', methods=['GET'])
def liveness_check():
    """Kubernetes liveness probe"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat()
    }), 200

# 就緒性檢查 (Readiness)
@health_bp.route('/ready', methods=['GET'])
async def readiness_check():
    """Kubernetes readiness probe"""
    try:
        from flask import current_app
        engine = current_app.config.get('ANALYSIS_ENGINE')
        
        if not engine:
            return jsonify({
                'status': 'not_ready',
                'reason': 'Engine not initialized'
            }), 503
        
        # 檢查關鍵組件
        health_status = await engine.get_health_status()
        critical_components = ['api', 'database', 'ai_providers']
        
        for component_name in critical_components:
            component = health_status['components'].get(component_name, {})
            if component.get('status') != 'healthy':
                return jsonify({
                    'status': 'not_ready',
                    'reason': f'{component_name} is {component.get("status", "unknown")}'
                }), 503
        
        return jsonify({
            'status': 'ready',
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'not_ready',
            'reason': str(e)
        }), 503

# 系統資源檢查
@health_bp.route('/resources', methods=['GET'])
@rate_limit(requests_per_minute=30)
def check_resources():
    """檢查系統資源使用情況"""
    try:
        # CPU 使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # 記憶體使用
        memory = psutil.virtual_memory()
        
        # 磁碟使用
        disk = psutil.disk_usage('/')
        
        # 網路連接數
        connections = len(psutil.net_connections())
        
        # 進程資訊
        process = psutil.Process(os.getpid())
        process_info = {
            'pid': process.pid,
            'cpu_percent': process.cpu_percent(),
            'memory_mb': round(process.memory_info().rss / (1024**2), 2),
            'threads': process.num_threads(),
            'open_files': len(process.open_files()),
            'connections': len(process.connections())
        }
        
        # 判斷資源狀態
        resource_status = 'healthy'
        warnings = []
        
        if cpu_percent > 80:
            resource_status = 'degraded'
            warnings.append(f'High CPU usage: {cpu_percent}%')
        
        if memory.percent > 85:
            resource_status = 'degraded'
            warnings.append(f'High memory usage: {memory.percent}%')
        
        if disk.percent > 90:
            resource_status = 'unhealthy'
            warnings.append(f'Critical disk usage: {disk.percent}%')
        
        return jsonify({
            'status': 'success',
            'data': {
                'resource_status': resource_status,
                'warnings': warnings,
                'cpu': {
                    'count': cpu_count,
                    'percent': cpu_percent,
                    'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
                },
                'memory': {
                    'total_gb': round(memory.total / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2),
                    'percent': memory.percent,
                    'used_gb': round(memory.used / (1024**3), 2)
                },
                'disk': {
                    'total_gb': round(disk.total / (1024**3), 2),
                    'free_gb': round(disk.free / (1024**3), 2),
                    'percent': disk.percent
                },
                'network': {
                    'connections': connections
                },
                'process': process_info,
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 依賴服務檢查
@health_bp.route('/dependencies', methods=['GET'])
@rate_limit(requests_per_minute=30)
async def check_dependencies():
    """檢查外部依賴服務的健康狀態"""
    try:
        from flask import current_app
        engine = current_app.config.get('ANALYSIS_ENGINE')
        
        dependencies = {
            'database': {'status': 'unknown', 'latency_ms': None},
            'redis': {'status': 'unknown', 'latency_ms': None},
            'anthropic_api': {'status': 'unknown', 'latency_ms': None},
            'openai_api': {'status': 'unknown', 'latency_ms': None}
        }
        
        if engine:
            # 檢查資料庫
            import time
            start = time.time()
            db_healthy = engine.storage.db.health_check()
            dependencies['database'] = {
                'status': 'healthy' if db_healthy else 'unhealthy',
                'latency_ms': round((time.time() - start) * 1000, 2)
            }
            
            # 檢查 Redis（如果配置了）
            redis_url = os.getenv('REDIS_URL')
            if redis_url:
                try:
                    import redis
                    r = redis.from_url(redis_url)
                    start = time.time()
                    r.ping()
                    dependencies['redis'] = {
                        'status': 'healthy',
                        'latency_ms': round((time.time() - start) * 1000, 2)
                    }
                except:
                    dependencies['redis']['status'] = 'unhealthy'
            
            # 檢查 AI 提供者
            for provider, wrapper in engine._wrappers.items():
                provider_name = f'{provider.value}_api'
                health = await wrapper.health_check()
                dependencies[provider_name] = {
                    'status': health['status'],
                    'latency_ms': None  # 可以實作 ping 測試
                }
        
        # 判斷整體狀態
        all_healthy = all(
            dep['status'] == 'healthy' 
            for dep in dependencies.values() 
            if dep['status'] != 'unknown'
        )
        
        return jsonify({
            'status': 'success',
            'data': {
                'overall_status': 'healthy' if all_healthy else 'degraded',
                'dependencies': dependencies,
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# 健康報告
@health_bp.route('/report', methods=['GET'])
@rate_limit(requests_per_minute=10)
async def generate_health_report():
    """生成完整的健康報告"""
    try:
        # 收集所有健康資訊
        basic_health = health_check()
        detailed_health = await health_check_detailed()
        resources = check_resources()
        dependencies = await check_dependencies()
        
        # 組合報告
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'overall_status': basic_health.json['status'],
                'components': basic_health.json.get('checks', {})
            },
            'detailed': detailed_health.json.get('data', {}),
            'resources': resources.json.get('data', {}),
            'dependencies': dependencies.json.get('data', {}),
            'recommendations': []
        }
        
        # 生成建議
        if report['resources']['cpu']['percent'] > 80:
            report['recommendations'].append('Consider scaling up CPU resources')
        
        if report['resources']['memory']['percent'] > 85:
            report['recommendations'].append('Memory usage is high, consider increasing memory')
        
        if report['resources']['disk']['percent'] > 90:
            report['recommendations'].append('Disk space is running low, cleanup required')
        
        return jsonify({
            'status': 'success',
            'data': report
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500