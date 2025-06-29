# 系統架構設計

## 目錄

1. [系統概述](#系統概述)
2. [架構原則](#架構原則)
3. [整體架構](#整體架構)
4. [核心組件](#核心組件)
5. [資料流程](#資料流程)
6. [技術棧](#技術棧)
7. [系統設計決策](#系統設計決策)
8. [擴展性設計](#擴展性設計)
9. [安全架構](#安全架構)
10. [效能設計](#效能設計)

## 系統概述

ANR/Tombstone AI 分析系統是一個專門用於分析 Android 應用程式崩潰日誌的智能系統。系統採用微服務架構，整合多個 AI 提供者，提供高效、準確的日誌分析服務。

### 主要特性

- **多 AI 提供者支援**：整合 Anthropic Claude 和 OpenAI GPT
- **串流處理**：支援大檔案的即時串流分析
- **智能成本控制**：自動選擇最優成本效益的模型
- **高可用性**：支援水平擴展和故障轉移
- **即時反饋**：通過 SSE 提供分析進度和結果

## 架構原則

### 1. 分層架構
- **表現層**：Web UI 和 API 端點
- **業務邏輯層**：分析引擎和業務規則
- **資料存取層**：資料庫和快取管理
- **基礎設施層**：AI 服務、訊息佇列等

### 2. 鬆耦合設計
- 組件之間通過明確定義的介面通信
- 使用依賴注入降低耦合度
- 支援熱插拔的 AI 提供者

### 3. 高內聚性
- 每個模組負責單一職責
- 相關功能組織在同一模組內
- 清晰的模組邊界

### 4. 可擴展性
- 水平擴展能力
- 模組化設計便於新增功能
- 支援多種部署模式

## 整體架構

```
┌─────────────────────────────────────────────────────────────────────┐
│                            客戶端層                                  │
├─────────────────┬─────────────────┬─────────────────┬──────────────┤
│   Web Browser   │   Mobile App    │   API Client    │   CLI Tool   │
└────────┬────────┴────────┬────────┴────────┬────────┴──────┬───────┘
         │                 │                 │                │
         └─────────────────┴─────────────────┴────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          API Gateway (Nginx)                         │
│  - 負載均衡  - SSL終止  - 速率限制  - 請求路由  - 靜態資源服務       │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         應用服務層 (Flask)                           │
├─────────────────┬─────────────────┬─────────────────┬──────────────┤
│   API Routes    │   Middleware    │   WebSocket/SSE │  Task Queue  │
│  - 分析端點     │  - 認證授權     │  - 即時通信     │ - 任務調度   │
│  - 狀態查詢     │  - 錯誤處理     │  - 進度推送     │ - 優先級管理 │
│  - 成本估算     │  - 日誌記錄     │  - 狀態更新     │ - 重試機制   │
└────────┬────────┴────────┬────────┴────────┬────────┴──────┬───────┘
         │                 │                 │                │
         └─────────────────┴─────────────────┴────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          核心業務層                                  │
├─────────────────┬─────────────────┬─────────────────┬──────────────┤
│ Analysis Engine │  AI Wrappers    │  Analyzers      │   Utils      │
│ - 工作流程管理  │ - Anthropic     │ - ANR分析器     │ - 狀態管理   │
│ - 模型選擇      │ - OpenAI        │ - Tombstone     │ - 成本計算   │
│ - 結果聚合      │ - 統一介面      │ - 模式匹配      │ - 快取管理   │
└────────┬────────┴────────┬────────┴────────┬────────┴──────┬───────┘
         │                 │                 │                │
         └─────────────────┴─────────────────┴────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          資料層                                      │
├─────────────────┬─────────────────┬─────────────────┬──────────────┤
│   PostgreSQL    │     Redis       │   File Storage  │  Monitoring  │
│  - 分析記錄     │  - 結果快取     │  - 日誌檔案     │ - Prometheus │
│  - 用戶資料     │  - 會話管理     │  - 臨時檔案     │ - Grafana    │
│  - 統計資訊     │  - 速率限制     │  - 報告存儲     │ - Sentry     │
└─────────────────┴─────────────────┴─────────────────┴──────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        外部服務層                                    │
├─────────────────────────────┬───────────────────────────────────────┤
│      Anthropic API          │           OpenAI API                  │
│  - Claude 3.5 Haiku         │      - GPT-4o-mini                   │
│  - Claude Sonnet 4          │      - GPT-4o                        │
│  - Claude Opus 4            │      - GPT-4-turbo                   │
└─────────────────────────────┴───────────────────────────────────────┘
```

## 核心組件

### 1. API Gateway (Nginx)

**職責**：
- 請求路由和負載均衡
- SSL/TLS 終止
- 靜態資源服務
- 速率限制和防護

**設計考量**：
- 高性能反向代理
- 支援 WebSocket/SSE
- 靈活的路由規則
- 內建快取機制

### 2. Analysis Engine

**架構**：
```python
class AiAnalysisEngine:
    def __init__(self):
        self.config = SystemConfig()
        self.status_manager = StatusManager()
        self.cache_manager = CacheManager()
        self.task_queue = TaskQueue()
        self.wrappers = {}  # AI provider wrappers
```

**主要功能**：
- 統一的分析入口
- 智能模型選擇
- 任務調度和管理
- 結果聚合和快取

### 3. AI Wrappers

**設計模式**：適配器模式

```python
class BaseAiLogWrapper(ABC):
    @abstractmethod
    async def analyze_anr(self, content: str, mode: AnalysisMode) -> AsyncIterator[str]:
        pass
    
    @abstractmethod
    async def analyze_tombstone(self, content: str, mode: AnalysisMode) -> AsyncIterator[str]:
        pass
```

**實現**：
- `AnthropicAiLogWrapper`
- `OpenAiLogWrapper`
- 未來可擴展其他提供者

### 4. 分析器組件

**層次結構**：
```
BaseAnalyzer
├── BaseANRAnalyzer
│   ├── AnthropicANRAnalyzer
│   └── OpenAIANRAnalyzer
└── BaseTombstoneAnalyzer
    ├── AnthropicTombstoneAnalyzer
    └── OpenAITombstoneAnalyzer
```

**關鍵特性**：
- 特定於日誌類型的分析邏輯
- Prompt 模板管理
- 結果格式化和標準化

### 5. 資料管理層

**組件**：
- **ORM Layer**: SQLAlchemy
- **快取層**: Redis + 記憶體快取
- **檔案存儲**: 本地/雲端存儲

**資料模型**：
```python
class AnalysisRecord(Base):
    id = Column(String, primary_key=True)
    created_at = Column(DateTime)
    log_type = Column(Enum(LogType))
    mode = Column(Enum(AnalysisMode))
    provider = Column(Enum(ModelProvider))
    content_hash = Column(String, index=True)
    result = Column(Text)
    tokens_used = Column(JSON)
    cost = Column(Float)
    duration = Column(Float)
```

## 資料流程

### 1. 分析請求流程

```
使用者上傳檔案
    │
    ▼
檔案驗證（大小、格式）
    │
    ▼
自動檢測日誌類型
    │
    ▼
成本估算
    │
    ▼
選擇分析模式和 AI 提供者
    │
    ▼
檢查快取
    │
    ├─── 命中 ──→ 返回快取結果
    │
    └─── 未命中
         │
         ▼
    創建分析任務
         │
         ▼
    分塊處理（如需要）
         │
         ▼
    調用 AI API
         │
         ▼
    串流接收結果
         │
         ▼
    聚合和格式化
         │
         ▼
    儲存結果和快取
         │
         ▼
    返回給使用者
```

### 2. SSE 通信流程

```
客戶端建立 SSE 連接
    │
    ▼
服務器接受連接
    │
    ▼
開始分析任務
    │
    ▼
┌─────────────┐
│  事件循環   │
├─────────────┤
│ 發送 start  │
│ 事件        │
│     ↓       │
│ 處理內容塊  │
│     ↓       │
│ 發送 content│
│ 事件        │
│     ↓       │
│ 更新進度    │
│     ↓       │
│ 發送 progress│
│ 事件        │
│     ↓       │
│ 檢查取消    │
│     ↓       │
│ 繼續/結束   │
└─────────────┘
    │
    ▼
發送 complete/error 事件
    │
    ▼
關閉連接
```

## 技術棧

### 後端技術

| 類別 | 技術 | 用途 |
|------|------|------|
| 語言 | Python 3.11+ | 主要開發語言 |
| Web 框架 | Flask 3.0+ | RESTful API |
| 異步支援 | asyncio, aiohttp | 異步 I/O 操作 |
| API 客戶端 | anthropic, openai | AI 服務整合 |
| 資料庫 | PostgreSQL 15+ | 主資料庫 |
| ORM | SQLAlchemy 2.0+ | 資料庫抽象層 |
| 快取 | Redis 7+ | 結果快取、會話管理 |
| 任務佇列 | 內建實現 | 異步任務處理 |
| 序列化 | Pydantic | 資料驗證和序列化 |

### 前端技術

| 類別 | 技術 | 用途 |
|------|------|------|
| 框架 | 原生 JavaScript | 輕量級實現 |
| UI 庫 | 自定義 CSS | 響應式設計 |
| 圖表 | Chart.js | 資料視覺化 |
| Markdown | marked.js | 結果渲染 |
| 語法高亮 | Prism.js | 程式碼高亮 |
| 即時通信 | EventSource API | SSE 支援 |

### 基礎設施

| 類別 | 技術 | 用途 |
|------|------|------|
| 容器化 | Docker | 應用打包 |
| 編排 | Docker Compose, K8s | 容器管理 |
| 反向代理 | Nginx | 負載均衡、SSL |
| 監控 | Prometheus + Grafana | 系統監控 |
| 日誌 | 結構化日誌 | 日誌管理 |
| CI/CD | GitHub Actions | 自動化部署 |

## 系統設計決策

### 1. 為什麼選擇 Flask 而非 FastAPI？

**決策理由**：
- 團隊熟悉度高
- 生態系統成熟
- SSE 支援簡單
- 足夠的異步支援

**權衡**：
- 犧牲了自動 API 文檔生成
- 需要額外的驗證邏輯

### 2. 為什麼使用多個 AI 提供者？

**優勢**：
- 避免單點故障
- 成本優化（不同場景選擇不同模型）
- 性能對比
- 特性互補

**挑戰**：
- 統一介面設計
- 結果標準化
- 成本管理複雜度

### 3. 快取策略設計

**多層快取**：
1. **記憶體快取**：最近使用的結果（LRU）
2. **Redis 快取**：跨實例共享的結果
3. **檔案快取**：大型結果的持久化存儲

**快取鍵設計**：
```python
cache_key = f"{content_hash}:{mode}:{model}:{version}"
```

### 4. 任務佇列設計

**設計特點**：
- 優先級佇列
- 自動重試機制
- 任務持久化
- 進度追蹤

**實現**：
```python
class TaskQueue:
    def __init__(self, max_concurrent: int):
        self.queue = asyncio.PriorityQueue()
        self.workers = []
        self.tasks = {}  # task_id -> Task
```

## 擴展性設計

### 1. 水平擴展

**無狀態設計**：
- API 服務器無狀態
- 會話存儲在 Redis
- 檔案存儲使用共享存儲

**負載均衡策略**：
- Round-robin 基本策略
- 基於 CPU 使用率的動態調整
- 健康檢查和自動故障轉移

### 2. 垂直擴展

**資源優化**：
- 連接池管理
- 異步處理
- 批次操作
- 查詢優化

### 3. 模組化擴展

**插件架構**：
```python
class AnalyzerPlugin(ABC):
    @abstractmethod
    def can_handle(self, log_type: str) -> bool:
        pass
    
    @abstractmethod
    async def analyze(self, content: str) -> AnalysisResult:
        pass
```

**擴展點**：
- 新增 AI 提供者
- 新增日誌類型分析器
- 自定義 Prompt 模板
- 結果後處理器

## 安全架構

### 1. 認證和授權

**多層認證**：
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  API Token  │ OR  │ JWT Token   │ OR  │  Session    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                    │
       └───────────────────┴────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Middleware  │
                    │ 驗證和解析  │
                    └─────────────┘
```

### 2. 資料安全

**加密策略**：
- 傳輸加密：HTTPS/TLS 1.3
- 存儲加密：敏感資料加密存儲
- API 金鑰加密：使用 KMS 或環境變數

**資料隔離**：
- 租戶級別的資料隔離
- 基於角色的存取控制（RBAC）
- 審計日誌

### 3. 輸入驗證

**驗證層次**：
1. **前端驗證**：基本格式檢查
2. **API 層驗證**：Pydantic 模型驗證
3. **業務層驗證**：業務規則檢查
4. **資料層驗證**：資料庫約束

### 4. 安全防護

**防護措施**：
- SQL 注入防護（ORM 參數化查詢）
- XSS 防護（內容轉義）
- CSRF 防護（Token 驗證）
- 速率限制（防止 DDoS）

## 效能設計

### 1. 異步處理

**異步架構**：
```python
async def analyze_large_file(content: str):
    chunks = split_into_chunks(content)
    tasks = []
    
    for chunk in chunks:
        task = asyncio.create_task(
            analyze_chunk(chunk)
        )
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    return merge_results(results)
```

### 2. 串流處理

**優勢**：
- 降低記憶體使用
- 改善響應時間
- 更好的用戶體驗

**實現**：
```python
async def stream_analysis():
    async for chunk in ai_client.stream_completion():
        yield format_sse_event('content', chunk)
```

### 3. 快取優化

**快取層級**：
| 層級 | 存儲 | TTL | 用途 |
|------|------|-----|------|
| L1 | 記憶體 | 5分鐘 | 熱點資料 |
| L2 | Redis | 24小時 | 共享快取 |
| L3 | 磁碟 | 7天 | 持久化存儲 |

### 4. 資料庫優化

**優化策略**：
- 適當的索引設計
- 查詢優化
- 連接池配置
- 讀寫分離（如需要）

**索引設計**：
```sql
-- 常用查詢索引
CREATE INDEX idx_created_at ON analysis_records(created_at DESC);
CREATE INDEX idx_user_created ON analysis_records(user_id, created_at DESC);
CREATE INDEX idx_content_hash ON analysis_records(content_hash);

-- 複合索引
CREATE INDEX idx_type_mode_provider ON analysis_records(log_type, mode, provider);
```

### 5. 監控和優化

**關鍵指標**：
- API 響應時間
- AI API 調用延遲
- 資料庫查詢時間
- 快取命中率
- 錯誤率

**性能基準**：
| 操作 | 目標時間 | 當前時間 |
|------|----------|----------|
| API 響應 | <100ms | 80ms |
| 快取查詢 | <10ms | 5ms |
| 資料庫查詢 | <50ms | 30ms |
| 檔案上傳 | <2s/MB | 1.5s/MB |

## 部署架構

### 1. 開發環境

```
┌─────────────┐
│   Docker    │
│  Compose    │
├─────────────┤
│ - API       │
│ - Web       │
│ - DB        │
│ - Redis     │
└─────────────┘
```

### 2. 生產環境

```
┌─────────────────────────────┐
│       Load Balancer         │
└──────────┬──────────────────┘
           │
    ┌──────┴──────┐
    │             │
┌───▼───┐    ┌───▼───┐
│ Node1 │    │ Node2 │
├───────┤    ├───────┤
│ API   │    │ API   │
│ Worker│    │ Worker│
└───┬───┘    └───┬───┘
    │             │
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │   Shared    │
    │  Services   │
    ├─────────────┤
    │ PostgreSQL  │
    │   Redis     │
    │   Storage   │
    └─────────────┘
```

### 3. 高可用架構

**主要組件**：
- 多可用區部署
- 資料庫主從複製
- Redis Sentinel
- 自動故障轉移

## 未來演進

### 短期目標（3-6個月）

1. **功能增強**
   - 批次分析 API
   - WebSocket 雙向通信
   - 更多 AI 模型支援

2. **性能優化**
   - GraphQL API
   - 更智能的快取策略
   - 預測性預載入

### 中期目標（6-12個月）

1. **架構演進**
   - 微服務拆分
   - 事件驅動架構
   - CQRS 模式

2. **智能化提升**
   - 自學習系統
   - 模式識別改進
   - 自動化建議

### 長期願景（1年+）

1. **平台化**
   - 插件市場
   - 開發者 API
   - SaaS 多租戶

2. **生態系統**
   - IDE 整合
   - CI/CD 整合
   - 監控告警整合

## 總結

ANR/Tombstone AI 分析系統採用現代化的架構設計，結合了微服務、事件驅動、串流處理等多種架構模式。系統設計充分考慮了可擴展性、高可用性、安全性和效能，為未來的發展奠定了堅實的基礎。

通過模組化和插件化的設計，系統可以輕鬆適應新的需求和技術變化，確保長期的技術競爭力和業務價值。