"""
完整使用範例
"""
import asyncio
from src.core.engine import AiAnalysisEngine
from src.analyzers.base import BaseApiConfig, ModelConfig, AnalysisMode,ModelProvider

async def complete_example():
    """完整的使用範例"""
    
    # 1. 初始化引擎
    print("=== 初始化系統 ===")
    engine = AiAnalysisEngine("config.yaml")
    
    # 啟動服務
    await engine.start()
    
    # 2. 檢查健康狀態
    print("\n=== 健康檢查 ===")
    health = await engine.get_health_status()
    print(f"系統狀態: {health['overall']['status']}")
    
    # 3. 讀取測試檔案
    with open("tests/fixtures/anr_sample.txt", "r") as f:
        anr_content = f.read()
    
    # 4. 估算成本
    print("\n=== 成本估算 ===")
    from src.utils.cost_calculator import CostCalculator
    calculator = CostCalculator()
    
    file_size_kb = len(anr_content) / 1024
    comparisons = calculator.compare_models_cost(file_size_kb, AnalysisMode.INTELLIGENT)
    
    print(f"檔案大小: {file_size_kb:.1f} KB")
    print("成本比較 (前3名):")
    for comp in comparisons[:3]:
        print(f"  {comp['model']}: ${comp['total_cost']:.2f} ({comp['analysis_time_estimate']:.1f}分鐘)")
    
    # 5. 設定狀態監聽
    print("\n=== 設定監聽器 ===")
    def status_callback(status):
        progress = status['progress']['progress_percentage']
        if progress > 0:
            print(f"進度: {progress:.1f}%")
        
        # 檢查回饋訊息
        if status['feedback']['messages']:
            latest = status['feedback']['messages'][-1]
            print(f"{latest['type']}: {latest['message']}")
    
    engine.add_status_listener(status_callback)
    
    # 6. 執行同步分析
    print("\n=== 執行同步分析 ===")
    result_chunks = []
    
    try:
        async for chunk in engine.analyze(
            anr_content,
            'anr',
            AnalysisMode.INTELLIGENT,
            ModelProvider.ANTHROPIC
        ):
            result_chunks.append(chunk)
            # 可以即時處理每個 chunk
            print(".", end="", flush=True)
        
        print("\n分析完成！")
        complete_result = ''.join(result_chunks)
        print(f"結果長度: {len(complete_result)} 字")
        
    except Exception as e:
        print(f"分析錯誤: {e}")
    
    # 7. 提交非同步任務
    print("\n=== 提交非同步任務 ===")
    task_id = await engine.submit_task(
        anr_content,
        'anr',
        AnalysisMode.QUICK,
        priority=1
    )
    print(f"任務 ID: {task_id}")
    
    # 等待任務完成
    while True:
        task_status = engine.get_task_status(task_id)
        if task_status['status'] in ['completed', 'failed']:
            break
        await asyncio.sleep(1)
    
    print(f"任務狀態: {task_status['status']}")
    
    # 8. 批次處理
    print("\n=== 批次處理範例 ===")
    tasks = []
    for i in range(3):
        task_id = await engine.submit_task(
            f"測試內容 {i}\n" * 100,
            'anr',
            AnalysisMode.QUICK,
            priority=i
        )
        tasks.append(task_id)
    
    print(f"已提交 {len(tasks)} 個任務")
    
    # 等待所有任務完成
    completed = 0
    while completed < len(tasks):
        completed = sum(
            1 for task_id in tasks 
            if engine.get_task_status(task_id)['status'] in ['completed', 'failed']
        )
        print(f"完成: {completed}/{len(tasks)}")
        await asyncio.sleep(1)
    
    # 9. 獲取最終統計
    print("\n=== 最終統計 ===")
    final_status = engine.get_status()
    print(f"總請求數: {final_status['api_usage']['requests_count']}")
    print(f"總輸入 Tokens: {final_status['api_usage']['input_tokens']:,}")
    print(f"總輸出 Tokens: {final_status['api_usage']['output_tokens']:,}")
    
    # 10. 關閉服務
    print("\n=== 關閉系統 ===")
    await engine.shutdown()


if __name__ == "__main__":
    asyncio.run(complete_example())