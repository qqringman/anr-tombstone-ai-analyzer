#!/usr/bin/env python3
"""
API 測試腳本
"""
import sys
import os
import json
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class APITester:
    """API 測試器"""
    
    def __init__(self, base_url: str = "http://localhost:5000", api_token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token or os.getenv('API_TOKEN')
        self.session = None
        self.results = []
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _get_headers(self) -> Dict[str, str]:
        """獲取請求標頭"""
        headers = {'Content-Type': 'application/json'}
        if self.api_token:
            headers['Authorization'] = f'Bearer {self.api_token}'
        return headers
    
    async def test_health_check(self):
        """測試健康檢查端點"""
        print("\n🏥 Testing health check endpoint...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/health") as response:
                data = await response.json()
                
                if response.status == 200:
                    print("  ✅ Health check: OK")
                    print(f"     - Status: {data.get('status')}")
                    print(f"     - Version: {data.get('version')}")
                    self.results.append(('health_check', True, None))
                else:
                    print(f"  ❌ Health check: Failed (HTTP {response.status})")
                    self.results.append(('health_check', False, f"HTTP {response.status}"))
                
                return data
        except Exception as e:
            print(f"  ❌ Health check: Error - {e}")
            self.results.append(('health_check', False, str(e)))
            return None
    
    async def test_cost_estimation(self):
        """測試成本估算端點"""
        print("\n💰 Testing cost estimation endpoint...")
        
        payload = {
            "file_size_kb": 1024,  # 1MB
            "mode": "intelligent"
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/ai/estimate-analysis-cost",
                headers=self._get_headers(),
                json=payload
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    print("  ✅ Cost estimation: OK")
                    if 'data' in data:
                        estimates = data['data'].get('cost_estimates', [])
                        for est in estimates[:3]:  # 顯示前3個
                            print(f"     - {est['model']}: ${est['total_cost']:.2f}")
                    self.results.append(('cost_estimation', True, None))
                else:
                    print(f"  ❌ Cost estimation: Failed (HTTP {response.status})")
                    self.results.append(('cost_estimation', False, f"HTTP {response.status}"))
                
                return data
        except Exception as e:
            print(f"  ❌ Cost estimation: Error - {e}")
            self.results.append(('cost_estimation', False, str(e)))
            return None
    
    async def test_basic_analysis(self):
        """測試基本分析端點"""
        print("\n🔍 Testing basic analysis endpoint...")
        
        # 使用簡單的測試 ANR 日誌
        test_anr = """
----- pid 12345 at 2024-01-15 10:30:45 -----
Cmd line: com.example.testapp
"main" prio=5 tid=1 Blocked
  | group="main" sCount=1 dsCount=0 flags=1
  | state=S schedstat=( 0 0 0 ) utm=0 stm=0 core=0 HZ=100
  at android.os.MessageQueue.nativePollOnce(Native Method)
  at android.os.MessageQueue.next(MessageQueue.java:336)
  at android.os.Looper.loop(Looper.java:174)
  at android.app.ActivityThread.main(ActivityThread.java:7356)
"""
        
        payload = {
            "content": test_anr,
            "log_type": "anr",
            "mode": "quick"
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/ai/analyze-with-ai",
                headers=self._get_headers(),
                json=payload,
                timeout=30
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    print("  ✅ Basic analysis: OK")
                    if 'data' in data and 'result' in data['data']:
                        result_preview = data['data']['result'][:100] + "..."
                        print(f"     - Result preview: {result_preview}")
                    self.results.append(('basic_analysis', True, None))
                else:
                    print(f"  ❌ Basic analysis: Failed (HTTP {response.status})")
                    if 'error' in data:
                        print(f"     - Error: {data['error']}")
                    self.results.append(('basic_analysis', False, f"HTTP {response.status}"))
                
                return data
        except Exception as e:
            print(f"  ❌ Basic analysis: Error - {e}")
            self.results.append(('basic_analysis', False, str(e)))
            return None
    
    async def test_sse_analysis(self):
        """測試 SSE 分析端點"""
        print("\n📡 Testing SSE analysis endpoint...")
        
        test_content = "Test ANR content for SSE"
        payload = {
            "content": test_content,
            "log_type": "anr",
            "mode": "quick"
        }
        
        try:
            # 測試 SSE 連接
            async with self.session.post(
                f"{self.base_url}/api/ai/analyze-with-cancellation",
                headers=self._get_headers(),
                json=payload
            ) as response:
                if response.status == 200:
                    print("  ✅ SSE endpoint: Connected")
                    
                    # 讀取幾個事件
                    event_count = 0
                    async for line in response.content:
                        if event_count >= 3:  # 只讀取前3個事件
                            break
                        
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            event_count += 1
                            try:
                                event_data = json.loads(line[6:])
                                print(f"     - Event {event_count}: {event_data.get('type', 'unknown')}")
                            except:
                                pass
                    
                    self.results.append(('sse_analysis', True, None))
                else:
                    print(f"  ❌ SSE analysis: Failed (HTTP {response.status})")
                    self.results.append(('sse_analysis', False, f"HTTP {response.status}"))
                
        except Exception as e:
            print(f"  ❌ SSE analysis: Error - {e}")
            self.results.append(('sse_analysis', False, str(e)))
    
    async def test_file_size_check(self):
        """測試檔案大小檢查"""
        print("\n📏 Testing file size check endpoint...")
        
        payload = {
            "file_size": 10 * 1024 * 1024  # 10MB
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/ai/check-file-size",
                headers=self._get_headers(),
                json=payload
            ) as response:
                data = await response.json()
                
                if response.status == 200:
                    print("  ✅ File size check: OK")
                    if 'data' in data:
                        print(f"     - Max size: {data['data']['max_size'] / 1024 / 1024:.0f}MB")
                        print(f"     - Is valid: {data['data']['is_valid']}")
                    self.results.append(('file_size_check', True, None))
                else:
                    print(f"  ❌ File size check: Failed (HTTP {response.status})")
                    self.results.append(('file_size_check', False, f"HTTP {response.status}"))
                
                return data
        except Exception as e:
            print(f"  ❌ File size check: Error - {e}")
            self.results.append(('file_size_check', False, str(e)))
            return None
    
    async def test_api_docs(self):
        """測試 API 文檔端點"""
        print("\n📚 Testing API documentation endpoint...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/docs") as response:
                data = await response.json()
                
                if response.status == 200:
                    print("  ✅ API docs: OK")
                    if 'endpoints' in data:
                        print(f"     - Endpoints documented: {len(data['endpoints'])}")
                    self.results.append(('api_docs', True, None))
                else:
                    print(f"  ❌ API docs: Failed (HTTP {response.status})")
                    self.results.append(('api_docs', False, f"HTTP {response.status}"))
                
                return data
        except Exception as e:
            print(f"  ❌ API docs: Error - {e}")
            self.results.append(('api_docs', False, str(e)))
            return None
    
    def print_summary(self):
        """列印測試摘要"""
        print("\n" + "="*50)
        print("📊 TEST SUMMARY")
        print("="*50)
        
        total = len(self.results)
        passed = sum(1 for _, success, _ in self.results if success)
        failed = total - passed
        
        print(f"\nTotal tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        
        if failed > 0:
            print("\n失敗的測試:")
            for name, success, error in self.results:
                if not success:
                    print(f"  - {name}: {error}")
        
        # 計算成功率
        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"\n成功率: {success_rate:.1f}%")
        
        return passed == total

async def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test ANR/Tombstone AI Analyzer API')
    parser.add_argument(
        '--url',
        default='http://localhost:5000',
        help='API base URL (default: http://localhost:5000)'
    )
    parser.add_argument(
        '--token',
        help='API token (can also use API_TOKEN env var)'
    )
    parser.add_argument(
        '--skip-analysis',
        action='store_true',
        help='Skip actual analysis tests (faster)'
    )
    
    args = parser.parse_args()
    
    print("🧪 ANR/Tombstone AI Analyzer API Test")
    print("="*50)
    print(f"API URL: {args.url}")
    print(f"Token: {'Configured' if args.token or os.getenv('API_TOKEN') else 'Not configured'}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    async with APITester(args.url, args.token) as tester:
        # 執行測試
        await tester.test_health_check()
        await tester.test_api_docs()
        await tester.test_file_size_check()
        await tester.test_cost_estimation()
        
        if not args.skip_analysis:
            await tester.test_basic_analysis()
            await tester.test_sse_analysis()
        
        # 顯示摘要
        success = tester.print_summary()
        
        # 設置退出碼
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())