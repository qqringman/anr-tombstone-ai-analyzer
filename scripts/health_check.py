#!/usr/bin/env python3
"""
系統健康檢查腳本
"""
import sys
import os
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.engine import AiAnalysisEngine
from src.storage.database import get_db
from src.config.system_config import get_system_config
from src.utils.health_checker import HealthStatus
import aiohttp

class SystemHealthChecker:
    """系統健康檢查器"""
    
    def __init__(self):
        self.config = get_system_config()
        self.results = {}
    
    async def check_all(self) -> Dict[str, Any]:
        """執行所有健康檢查"""
        print("🔍 Starting system health check...\n")
        
        # 檢查配置
        await self.check_configuration()
        
        # 檢查資料庫
        await self.check_database()
        
        # 檢查 AI 引擎
        await self.check_ai_engine()
        
        # 檢查 API 服務
        await self.check_api_service()
        
        # 檢查檔案系統
        await self.check_filesystem()
        
        # 檢查外部服務
        await self.check_external_services()
        
        # 總結
        overall_status = self.calculate_overall_status()
        self.results['overall'] = overall_status
        self.results['timestamp'] = datetime.now().isoformat()
        
        return self.results
    
    async def check_configuration(self):
        """檢查系統配置"""
        print("📋 Checking configuration...")
        
        try:
            is_valid, errors = self.config.validate_config()
            
            if is_valid:
                self.results['configuration'] = {
                    'status': 'healthy',
                    'message': 'Configuration is valid',
                    'environment': self.config.system.environment,
                    'version': self.config.system.version
                }
                print("  ✅ Configuration: OK")
            else:
                self.results['configuration'] = {
                    'status': 'unhealthy',
                    'message': 'Configuration errors found',
                    'errors': errors
                }
                print("  ❌ Configuration: FAILED")
                for error in errors:
                    print(f"     - {error}")
        except Exception as e:
            self.results['configuration'] = {
                'status': 'error',
                'message': str(e)
            }
            print(f"  ❌ Configuration: ERROR - {e}")
    
    async def check_database(self):
        """檢查資料庫連接"""
        print("\n💾 Checking database...")
        
        try:
            db = get_db()
            if db.health_check():
                # 檢查資料表
                with db.session() as session:
                    table_count = len(db.engine.table_names())
                
                self.results['database'] = {
                    'status': 'healthy',
                    'message': 'Database connection successful',
                    'table_count': table_count,
                    'url': db._mask_connection_string(db.database_url)
                }
                print("  ✅ Database: OK")
                print(f"     - Tables: {table_count}")
            else:
                self.results['database'] = {
                    'status': 'unhealthy',
                    'message': 'Database connection failed'
                }
                print("  ❌ Database: FAILED")
        except Exception as e:
            self.results['database'] = {
                'status': 'error',
                'message': str(e)
            }
            print(f"  ❌ Database: ERROR - {e}")
    
    async def check_ai_engine(self):
        """檢查 AI 引擎"""
        print("\n🤖 Checking AI engine...")
        
        try:
            engine = AiAnalysisEngine()
            
            # 獲取健康狀態
            health_status = await engine.get_health_status()
            
            # 檢查各個組件
            components_healthy = all(
                comp['status'] == 'healthy' 
                for comp in health_status['components'].values()
            )
            
            if components_healthy:
                providers = engine.get_status()['available_providers']
                self.results['ai_engine'] = {
                    'status': 'healthy',
                    'message': 'AI engine is operational',
                    'available_providers': providers,
                    'components': health_status['components']
                }
                print("  ✅ AI Engine: OK")
                print(f"     - Providers: {', '.join(providers)}")
            else:
                self.results['ai_engine'] = {
                    'status': 'degraded',
                    'message': 'Some components are unhealthy',
                    'components': health_status['components']
                }
                print("  ⚠️  AI Engine: DEGRADED")
                for name, comp in health_status['components'].items():
                    if comp['status'] != 'healthy':
                        print(f"     - {name}: {comp['message']}")
            
            await engine.shutdown()
            
        except Exception as e:
            self.results['ai_engine'] = {
                'status': 'error',
                'message': str(e)
            }
            print(f"  ❌ AI Engine: ERROR - {e}")
    
    async def check_api_service(self):
        """檢查 API 服務"""
        print("\n🌐 Checking API service...")
        
        api_url = f"http://localhost:{self.config.get('api', {}).get('port', 5000)}/api/health"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.results['api_service'] = {
                            'status': 'healthy',
                            'message': 'API service is running',
                            'endpoint': api_url,
                            'response': data
                        }
                        print("  ✅ API Service: OK")
                    else:
                        self.results['api_service'] = {
                            'status': 'unhealthy',
                            'message': f'API returned status {response.status}',
                            'endpoint': api_url
                        }
                        print(f"  ❌ API Service: HTTP {response.status}")
        except aiohttp.ClientError as e:
            self.results['api_service'] = {
                'status': 'unavailable',
                'message': 'API service is not running',
                'endpoint': api_url,
                'error': str(e)
            }
            print("  ⚠️  API Service: NOT RUNNING")
        except Exception as e:
            self.results['api_service'] = {
                'status': 'error',
                'message': str(e)
            }
            print(f"  ❌ API Service: ERROR - {e}")
    
    async def check_filesystem(self):
        """檢查檔案系統"""
        print("\n📁 Checking filesystem...")
        
        try:
            # 檢查必要的目錄
            directories = {
                'logs': Path('logs'),
                'cache': Path('.cache'),
                'data': Path('data'),
                'uploads': Path('uploads')
            }
            
            all_good = True
            issues = []
            
            for name, path in directories.items():
                if not path.exists():
                    path.mkdir(parents=True, exist_ok=True)
                    issues.append(f"{name} directory created")
                
                # 檢查寫入權限
                test_file = path / '.write_test'
                try:
                    test_file.write_text('test')
                    test_file.unlink()
                except Exception as e:
                    all_good = False
                    issues.append(f"{name} directory not writable: {e}")
            
            if all_good:
                self.results['filesystem'] = {
                    'status': 'healthy',
                    'message': 'All directories accessible',
                    'notes': issues if issues else None
                }
                print("  ✅ Filesystem: OK")
                for issue in issues:
                    print(f"     - {issue}")
            else:
                self.results['filesystem'] = {
                    'status': 'unhealthy',
                    'message': 'Filesystem issues found',
                    'issues': issues
                }
                print("  ❌ Filesystem: FAILED")
                for issue in issues:
                    print(f"     - {issue}")
        
        except Exception as e:
            self.results['filesystem'] = {
                'status': 'error',
                'message': str(e)
            }
            print(f"  ❌ Filesystem: ERROR - {e}")
    
    async def check_external_services(self):
        """檢查外部服務"""
        print("\n🌍 Checking external services...")
        
        services = {
            'Anthropic API': 'https://api.anthropic.com/v1/messages',
            'OpenAI API': 'https://api.openai.com/v1/models'
        }
        
        results = {}
        
        for name, url in services.items():
            try:
                async with aiohttp.ClientSession() as session:
                    # 只檢查連接，不需要真的調用 API
                    async with session.head(url, timeout=5) as response:
                        if response.status < 500:
                            results[name] = {
                                'status': 'reachable',
                                'response_time': response.headers.get('X-Response-Time', 'N/A')
                            }
                            print(f"  ✅ {name}: REACHABLE")
                        else:
                            results[name] = {
                                'status': 'error',
                                'http_status': response.status
                            }
                            print(f"  ❌ {name}: HTTP {response.status}")
            except Exception as e:
                results[name] = {
                    'status': 'unreachable',
                    'error': str(e)
                }
                print(f"  ⚠️  {name}: UNREACHABLE")
        
        self.results['external_services'] = results
    
    def calculate_overall_status(self) -> Dict[str, Any]:
        """計算整體狀態"""
        statuses = []
        
        for component, result in self.results.items():
            if isinstance(result, dict) and 'status' in result:
                status = result['status']
                if status == 'healthy':
                    statuses.append(2)
                elif status in ['degraded', 'reachable']:
                    statuses.append(1)
                else:
                    statuses.append(0)
        
        if not statuses:
            return {'status': 'unknown', 'score': 0}
        
        avg_score = sum(statuses) / len(statuses)
        
        if avg_score >= 1.8:
            status = 'healthy'
            emoji = '✅'
        elif avg_score >= 1.0:
            status = 'degraded'
            emoji = '⚠️'
        else:
            status = 'unhealthy'
            emoji = '❌'
        
        return {
            'status': status,
            'score': round(avg_score, 2),
            'emoji': emoji
        }

async def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Check system health')
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output'
    )
    
    args = parser.parse_args()
    
    checker = SystemHealthChecker()
    results = await checker.check_all()
    
    print("\n" + "="*50)
    print("📊 HEALTH CHECK SUMMARY")
    print("="*50)
    
    overall = results['overall']
    print(f"\n{overall['emoji']} Overall Status: {overall['status'].upper()}")
    print(f"   Health Score: {overall['score']}/2.0")
    print(f"   Timestamp: {results['timestamp']}")
    
    if args.json:
        print("\n📄 JSON Output:")
        print(json.dumps(results, indent=2))
    
    # 設置退出碼
    if overall['status'] == 'healthy':
        sys.exit(0)
    elif overall['status'] == 'degraded':
        sys.exit(1)
    else:
        sys.exit(2)

if __name__ == "__main__":
    asyncio.run(main())