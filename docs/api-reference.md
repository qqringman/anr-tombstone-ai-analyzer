# API 參考文檔

ANR/Tombstone AI 分析系統提供 RESTful API 和 Server-Sent Events (SSE) 端點。

## 基礎資訊

### Base URL
```
開發環境: http://localhost:5000/api
生產環境: https://your-domain.com/api
```

### 認證

系統支援多種認證方式：

1. **API Token**（簡單認證）
```http
Authorization: Bearer YOUR_API_TOKEN
```

2. **JWT Token**（進階認證）
```http
Authorization: Bearer YOUR_JWT_TOKEN
```

3. **Session Token**（網頁應用）
```http
X-Session-Token: YOUR_SESSION_TOKEN
```

### 請求格式

- Content-Type: `application/json`
- 字符編碼: `UTF-8`

### 響應格式

成功響應：
```json
{
  "status": "success",
  "data": {
    // 響應資料
  },
  "timestamp": "2025-01-15T10:30:45.123Z"
}
```

錯誤響應：
```json
{
  "status": "error",
  "error": {
    "type": "ValidationError",
    "message": "錯誤描述",
    "code": 400,
    "details": {}
  },
  "request_id": "req_12345"
}
```

## API 端點

### 健康檢查

#### GET /api/health

檢查系統健康狀態。

**請求範例：**
```bash
curl -X GET http://localhost:5000/api/health
```

**響應範例：**
```json
{
  "status": "healthy",
  "service": "ANR/Tombstone AI Analyzer",
  "timestamp": "2025-01-15T10:30:45.123Z",
  "version": "1.0.0",
  "checks": {
    "api": "ok",
    "database": "ok",
    "redis": "ok",
    "ai_providers": ["anthropic", "openai"]
  }
}
```

#### GET /api/health/detailed

獲取詳細的健康檢查資訊。

**響應包含：**
- 各組件狀態
- 系統資源使用情況
- API 可用性
- 錯誤率統計

### 分析 API

#### POST /api/ai/analyze-with-ai

執行同步分析（適合小檔案）。

**請求參數：**
```json
{
  "content": "string",     // 必填：日誌內容
  "log_type": "string",    // 必填：anr 或 tombstone
  "mode": "string",        // 可選：quick/intelligent/large_file/max_token
  "provider": "string"     // 可選：anthropic/openai
}
```

**請求範例：**
```bash
curl -X POST http://localhost:5000/api/ai/analyze-with-ai \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -d '{
    "content": "----- pid 12345 at 2024-01-15 10:30:45 -----\n...",
    "log_type": "anr",
    "mode": "intelligent"
  }'
```

**響應範例：**
```json
{
  "status": "success",
  "data": {
    "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
    "log_type": "anr",
    "mode": "intelligent",
    "result": "# ANR 分析報告\n\n## 問題摘要\n...",
    "tokens_used": {
      "input": 1500,
      "output": 800
    },
    "cost": 0.25,
    "duration": 3.5
  }
}
```

#### POST /api/ai/analyze-with-cancellation

執行可取消的串流分析（SSE）。

**請求參數：**
同 `/api/ai/analyze-with-ai`

**SSE 事件類型：**

1. **start** - 分析開始
```json
{
  "type": "start",
  "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-01-15T10:30:45.123Z"
}
```

2. **content** - 分析內容片段
```json
{
  "type": "content",
  "content": "分析內容片段..."
}
```

3. **progress** - 進度更新
```json
{
  "type": "progress",
  "progress": {
    "progress_percentage": 45.5,
    "current_chunk": 2,
    "total_chunks": 5,
    "processed_tokens": 1200
  }
}
```

4. **feedback** - 狀態反饋
```json
{
  "type": "feedback",
  "level": "info",
  "message": "正在分析主線程狀態..."
}
```

5. **complete** - 分析完成
```json
{
  "type": "complete",
  "total_tokens": 2300,
  "total_cost": 0.25,
  "duration_seconds": 5.2
}
```

6. **error** - 錯誤事件
```json
{
  "type": "error",
  "error_type": "TokenLimitExceeded",
  "message": "超過 token 限制"
}
```

**JavaScript 客戶端範例：**
```javascript
const eventSource = new EventSource('/api/ai/analyze-with-cancellation', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_API_TOKEN'
  },
  body: JSON.stringify({
    content: logContent,
    log_type: 'anr',
    mode: 'intelligent'
  })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data.type, data);
};

eventSource.onerror = (error) => {
  console.error('SSE Error:', error);
  eventSource.close();
};
```

#### POST /api/ai/cancel-analysis/{analysis_id}

取消進行中的分析。

**請求參數：**
```json
{
  "reason": "string"  // 可選：取消原因
}
```

**響應範例：**
```json
{
  "status": "success",
  "message": "分析已取消"
}
```

### 成本估算

#### POST /api/ai/estimate-analysis-cost

估算分析成本。

**請求參數：**
```json
{
  "file_size_kb": 1024,    // 必填：檔案大小（KB）
  "mode": "intelligent"     // 可選：分析模式
}
```

**響應範例：**
```json
{
  "status": "success",
  "data": {
    "file_info": {
      "size_kb": 1024,
      "estimated_tokens": 410000
    },
    "cost_estimates": [
      {
        "provider": "anthropic",
        "model": "claude-3-5-haiku-20241022",
        "tier": 2,
        "total_cost": 0.15,
        "input_cost": 0.10,
        "output_cost": 0.05,
        "analysis_time_estimate": 2.5,
        "is_within_budget": true,
        "quality_rating": 3,
        "speed_rating": 5
      }
    ],
    "recommended_mode": "intelligent"
  }
}
```

### 檔案處理

#### POST /api/ai/check-file-size

檢查檔案大小是否符合限制。

**請求參數：**
```json
{
  "file_size": 10485760  // 檔案大小（位元組）
}
```

**響應範例：**
```json
{
  "status": "success",
  "data": {
    "file_size": 10485760,
    "max_size": 20971520,
    "is_valid": true,
    "message": "File size is acceptable"
  }
}
```

### 任務管理

#### GET /api/tasks/{task_id}

獲取任務狀態。

**響應範例：**
```json
{
  "status": "success",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "running",
    "created_at": "2025-01-15T10:30:45.123Z",
    "mode": "intelligent",
    "log_type": "anr",
    "progress": 45.5
  }
}
```

#### GET /api/tasks

列出所有任務。

**查詢參數：**
- `status`: 篩選狀態（pending/running/completed/failed/cancelled）
- `limit`: 限制數量（預設 20）
- `offset`: 偏移量（用於分頁）

### 統計資訊

#### GET /api/stats/usage

獲取使用統計。

**查詢參數：**
- `start_date`: 開始日期（ISO 8601）
- `end_date`: 結束日期（ISO 8601）
- `provider`: 篩選提供者

**響應範例：**
```json
{
  "status": "success",
  "data": {
    "total_cost": 125.50,
    "total_requests": 500,
    "total_input_tokens": 5000000,
    "total_output_tokens": 2000000,
    "by_provider": {
      "anthropic": {
        "cost": 75.30,
        "requests": 300
      },
      "openai": {
        "cost": 50.20,
        "requests": 200
      }
    }
  }
}
```

#### GET /api/stats/health-metrics

獲取系統健康指標。

**響應包含：**
- CPU 和記憶體使用率
- 活躍分析數
- 佇列大小
- 快取命中率
- API 可用性

### 管理 API

#### POST /api/admin/cache/clear

清除快取（需要管理員權限）。

**請求參數：**
```json
{
  "type": "all"  // all/memory/disk/expired
}
```

#### POST /api/admin/tasks/cleanup

清理舊任務（需要管理員權限）。

**請求參數：**
```json
{
  "older_than_hours": 24
}
```

## 錯誤碼

| 錯誤碼 | 類型 | 說明 |
|--------|------|------|
| 400 | Bad Request | 請求參數錯誤 |
| 401 | Unauthorized | 未認證或認證失敗 |
| 402 | Payment Required | 預算超限 |
| 403 | Forbidden | 無權限訪問 |
| 404 | Not Found | 資源不存在 |
| 413 | Payload Too Large | 檔案過大 |
| 429 | Too Many Requests | 速率限制 |
| 500 | Internal Server Error | 伺服器錯誤 |
| 502 | Bad Gateway | AI 服務不可用 |
| 503 | Service Unavailable | 服務暫時不可用 |
| 504 | Gateway Timeout | 分析超時 |

## 速率限制

預設限制：
- 每分鐘：60 請求
- 每小時：1000 請求
- 突發：10 請求

速率限制響應頭：
```
X-RateLimit-Limit-Minute: 60
X-RateLimit-Remaining-Minute: 45
X-RateLimit-Reset-Minute: 1673786400
```

## SDK 範例

### Python SDK

```python
import aiohttp
import asyncio

class ANRAnalyzerClient:
    def __init__(self, base_url, api_token):
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        }
    
    async def analyze(self, content, log_type='anr', mode='intelligent'):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{self.base_url}/api/ai/analyze-with-ai',
                headers=self.headers,
                json={
                    'content': content,
                    'log_type': log_type,
                    'mode': mode
                }
            ) as response:
                return await response.json()

# 使用範例
client = ANRAnalyzerClient('http://localhost:5000', 'YOUR_API_TOKEN')
result = await client.analyze(log_content)
```

### JavaScript/TypeScript SDK

```typescript
class ANRAnalyzerClient {
  constructor(
    private baseUrl: string,
    private apiToken: string
  ) {}

  async analyze(
    content: string,
    logType: 'anr' | 'tombstone' = 'anr',
    mode: string = 'intelligent'
  ): Promise<AnalysisResult> {
    const response = await fetch(`${this.baseUrl}/api/ai/analyze-with-ai`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        content,
        log_type: logType,
        mode
      })
    });
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    
    return response.json();
  }
  
  analyzeStream(
    content: string,
    onProgress: (event: AnalysisEvent) => void
  ): EventSource {
    const params = new URLSearchParams({
      content,
      log_type: 'anr',
      mode: 'intelligent'
    });
    
    const eventSource = new EventSource(
      `${this.baseUrl}/api/ai/analyze-with-cancellation?${params}`
    );
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onProgress(data);
    };
    
    return eventSource;
  }
}
```

## Webhook 整合

系統支援 Webhook 通知：

```json
{
  "event": "analysis.completed",
  "data": {
    "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "cost": 0.25,
    "duration": 5.2
  },
  "timestamp": "2025-01-15T10:30:45.123Z"
}
```

支援的事件：
- `analysis.started`
- `analysis.completed`
- `analysis.failed`
- `analysis.cancelled`
- `budget.exceeded`
- `error.critical`

## 最佳實踐

1. **錯誤處理**
   - 實作重試機制
   - 處理網路超時
   - 記錄錯誤詳情

2. **效能優化**
   - 使用串流 API 處理大檔案
   - 實作客戶端快取
   - 批次處理請求

3. **安全性**
   - 使用 HTTPS
   - 定期輪換 API 金鑰
   - 驗證所有輸入

4. **監控**
   - 追蹤 API 使用量
   - 監控響應時間
   - 設定告警閾值