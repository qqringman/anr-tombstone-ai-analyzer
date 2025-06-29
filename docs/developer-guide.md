# 開發者指南

本指南幫助開發者理解系統架構、擴展功能和貢獻代碼。

## 系統架構

### 整體架構

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Web UI    │────▶│   API       │────▶│   Engine    │
└─────────────┘     └─────────────┘     └─────────────┘
                            │                    │
                            ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │   Storage   │     │ AI Wrappers │
                    └─────────────┘     └─────────────┘
                            │                    │
                            ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  Database   │     │ AI Providers│
                    └─────────────┘     └─────────────┘
```

### 核心組件

#### 1. API 層 (`src/api/`)
- Flask 應用程式
- RESTful 端點
- SSE 支援
- 中間件（認證、速率限制、錯誤處理）

#### 2. 核心引擎 (`src/core/`)
- `AiAnalysisEngine`: 主要分析引擎
- `CancellationToken`: 取消機制
- 異常處理
- 模型定義

#### 3. 分析器 (`src/analyzers/`)
- 基礎分析器類
- ANR 分析器（Anthropic/OpenAI）
- Tombstone 分析器（Anthropic/OpenAI）

#### 4. 包裝器 (`src/wrappers/`)
- AI 提供者包裝器
- 統一的 API 介面
- 成本計算
- 統計追蹤

#### 5. 工具模組 (`src/utils/`)
- 狀態管理
- 快取管理
- 成本計算
- 並行處理
- 日誌系統

## 開發環境設置

### 1. 克隆專案

```bash
git clone https://github.com/your-org/anr-tombstone-ai-analyzer.git
cd anr-tombstone-ai-analyzer
```

### 2. 設置虛擬環境

```bash
# 創建虛擬環境
python -m venv venv

# 啟動虛擬環境
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# 安裝開發依賴
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. 配置開發環境

```bash
# 複製環境變數
cp .env.example .env.development

# 編輯配置
nano .env.development
```

開發環境配置：
```bash
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=DEBUG
DATABASE_URL=sqlite:///data/dev.db
```

### 4. 初始化資料庫

```bash
# 運行資料庫遷移
python scripts/setup_db.py --dev

# 創建測試資料
python scripts/create_sample_data.py
```

### 5. 啟動開發服務器

```bash
# 啟動 API 服務器
python -m src.api.app

# 啟動前端開發服務器
cd web
python -m http.server 5566
```

## 代碼結構詳解

### 添加新的 AI 提供者

1. **創建配置類** (`src/config/new_provider_config.py`):

```python
from typing import Dict
from .base import BaseApiConfig, ModelConfig, AnalysisMode

class NewProviderConfig(BaseApiConfig):
    """新 AI 提供者配置"""
    
    base_url: str = "https://api.newprovider.com"
    
    models: Dict[str, ModelConfig] = {
        "model-name": ModelConfig(
            name="model-name",
            max_tokens=8192,
            input_cost_per_1k=1.0,
            output_cost_per_1k=2.0,
            context_window=100000,
            supports_streaming=True
        )
    }
    
    default_model: str = "model-name"
    
    mode_model_mapping: Dict[AnalysisMode, str] = {
        AnalysisMode.QUICK: "model-name-fast",
        AnalysisMode.INTELLIGENT: "model-name",
        # ...
    }
```

2. **創建分析器** (`src/analyzers/anr/new_provider_anr.py`):

```python
from typing import AsyncIterator, Optional
from .base_anr import BaseANRAnalyzer
from ...config.base import AnalysisMode, ModelProvider

class NewProviderANRAnalyzer(BaseANRAnalyzer):
    """新提供者 ANR 分析器"""
    
    async def analyze(self, 
                     content: str, 
                     mode: AnalysisMode,
                     cancellation_token: Optional[CancellationToken] = None
                     ) -> AsyncIterator[str]:
        """執行分析"""
        # 實作分析邏輯
        pass
```

3. **創建包裝器** (`src/wrappers/new_provider_wrapper.py`):

```python
from .base_wrapper import BaseAiLogWrapper
from ..config.base import ModelProvider

class NewProviderWrapper(BaseAiLogWrapper):
    """新提供者包裝器"""
    
    @property
    def provider(self) -> ModelProvider:
        return ModelProvider.NEW_PROVIDER
    
    async def analyze_anr(self, content: str, mode: AnalysisMode,
                         cancellation_token: Optional[CancellationToken] = None
                         ) -> AsyncIterator[str]:
        # 實作 ANR 分析
        pass
```

### 添加新的分析模式

1. **更新枚舉** (`src/config/base.py`):

```python
class AnalysisMode(Enum):
    QUICK = "quick"
    INTELLIGENT = "intelligent"
    LARGE_FILE = "large_file"
    MAX_TOKEN = "max_token"
    CUSTOM = "custom"  # 新模式
```

2. **更新配置** (`config.yaml`):

```yaml
analysis_modes:
  custom:
    description: "自定義分析模式"
    chunk_size: 100000
    max_tokens: 5000
    timeout: 180
```

3. **更新 UI** (`web/index.html`):

```html
<label class="radio-card">
    <input type="radio" name="analysisMode" value="custom">
    <div class="radio-content">
        <h4>自定義分析</h4>
        <p>特定場景的優化分析</p>
    </div>
</label>
```

### 自定義 Prompt 模板

1. **創建 Prompt 檔案** (`src/prompts/data/custom_prompts.yaml`):

```yaml
custom_anr_quick:
  name: "Custom ANR Quick Analysis"
  description: "自定義的快速 ANR 分析"
  system_prompt: |
    你是專門分析 ANR 的 Android 專家。
    請提供簡潔但準確的分析。
  user_prompt: |
    分析以下 ANR 日誌：
    
    關鍵資訊：
    - PID: {pid}
    - 包名: {package}
    - 主線程狀態: {main_thread_state}
    
    日誌內容：
    {content}
  variables:
    pid: ""
    package: ""
    main_thread_state: ""
    content: ""
  required_variables: ["content"]
  tags: ["anr", "custom", "quick"]
```

2. **使用自定義 Prompt**:

```python
from src.prompts.manager import get_prompt_manager

# 獲取 prompt
prompt_manager = get_prompt_manager()
template = prompt_manager.get_prompt("custom_anr_quick", mode)

# 渲染 prompt
rendered = template.render(
    content=log_content,
    pid="12345",
    package="com.example.app",
    main_thread_state="Blocked"
)
```

## API 開發

### 添加新端點

1. **創建路由** (`src/api/routes/custom.py`):

```python
from flask import Blueprint, request, jsonify
from ...core.engine import AiAnalysisEngine

custom_bp = Blueprint('custom', __name__)

@custom_bp.route('/api/custom/analyze', methods=['POST'])
async def custom_analyze():
    """自定義分析端點"""
    try:
        data = request.get_json()
        
        # 驗證輸入
        if not data.get('content'):
            return jsonify({
                'status': 'error',
                'message': 'Content is required'
            }), 400
        
        # 執行分析
        engine = AiAnalysisEngine()
        result = await engine.analyze(
            content=data['content'],
            log_type=data.get('log_type', 'anr'),
            mode=data.get('mode', 'custom')
        )
        
        return jsonify({
            'status': 'success',
            'data': {'result': result}
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
```

2. **註冊路由** (`src/api/app.py`):

```python
from .routes.custom import custom_bp

app.register_blueprint(custom_bp)
```

### 中間件開發

創建自定義中間件 (`src/api/middleware/custom.py`):

```python
from functools import wraps
from flask import request, g

def track_usage(f):
    """追蹤 API 使用的中間件"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        # 記錄請求開始時間
        g.start_time = time.time()
        
        # 執行原函數
        result = await f(*args, **kwargs)
        
        # 計算執行時間
        duration = time.time() - g.start_time
        
        # 記錄到資料庫
        await record_api_usage(
            endpoint=request.endpoint,
            duration=duration,
            status_code=result.status_code
        )
        
        return result
    
    return decorated_function
```

## 測試

### 單元測試

1. **測試分析器** (`tests/unit/test_custom_analyzer.py`):

```python
import pytest
from src.analyzers.anr.custom_anr import CustomANRAnalyzer
from src.config.base import AnalysisMode

@pytest.mark.asyncio
async def test_custom_analyzer():
    """測試自定義分析器"""
    analyzer = CustomANRAnalyzer(config)
    
    content = "test ANR log content"
    mode = AnalysisMode.QUICK
    
    result_chunks = []
    async for chunk in analyzer.analyze(content, mode):
        result_chunks.append(chunk)
    
    assert len(result_chunks) > 0
    assert "ANR" in ''.join(result_chunks)
```

2. **測試 API** (`tests/integration/test_custom_api.py`):

```python
import pytest
from src.api.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_custom_endpoint(client):
    """測試自定義端點"""
    response = client.post('/api/custom/analyze', json={
        'content': 'test content',
        'log_type': 'anr'
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
```

### 整合測試

運行完整測試套件：

```bash
# 運行所有測試
pytest

# 運行特定測試
pytest tests/unit/test_analyzers.py

# 顯示覆蓋率
pytest --cov=src --cov-report=html
```

## 部署

### Docker 部署

1. **構建映像**:

```bash
docker build -t anr-analyzer:latest .
```

2. **運行容器**:

```bash
docker run -d \
  -p 5000:5000 \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e DATABASE_URL=$DATABASE_URL \
  anr-analyzer:latest
```

### Kubernetes 部署

1. **創建部署配置** (`k8s/deployment.yaml`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: anr-analyzer
spec:
  replicas: 3
  selector:
    matchLabels:
      app: anr-analyzer
  template:
    metadata:
      labels:
        app: anr-analyzer
    spec:
      containers:
      - name: api
        image: anr-analyzer:latest
        ports:
        - containerPort: 5000
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: anthropic-key
```

2. **部署到 K8s**:

```bash
kubectl apply -f k8s/
```

## 效能優化

### 1. 快取優化

```python
# 使用 Redis 快取
from src.utils.cache_manager import CacheManager

cache = CacheManager(backend='redis')

# 快取分析結果
@cache.memoize(ttl=3600)
async def analyze_with_cache(content: str, mode: str):
    return await engine.analyze(content, 'anr', mode)
```

### 2. 並行處理

```python
from src.utils.parallel_processor import ParallelProcessor

processor = ParallelProcessor(max_concurrent=5)

# 批次處理多個檔案
results = await processor.map_async(
    analyze_file,
    file_list
)
```

### 3. 資料庫優化

```python
# 使用索引
class AnalysisRecord(Base):
    __tablename__ = 'analysis_records'
    
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, index=True)
    content_hash = Column(String, index=True)
    
    __table_args__ = (
        Index('idx_created_hash', 'created_at', 'content_hash'),
    )
```

## 監控和日誌

### 1. 結構化日誌

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 記錄分析事件
logger.log_analysis(
    "info",
    "Analysis started",
    analysis_id=analysis_id,
    mode=mode,
    file_size=file_size
)
```

### 2. 指標收集

```python
from prometheus_client import Counter, Histogram

# 定義指標
analysis_counter = Counter(
    'analysis_total',
    'Total number of analyses',
    ['log_type', 'mode', 'provider']
)

analysis_duration = Histogram(
    'analysis_duration_seconds',
    'Analysis duration in seconds',
    ['log_type', 'mode']
)

# 使用指標
analysis_counter.labels(
    log_type='anr',
    mode='quick',
    provider='anthropic'
).inc()
```

### 3. 健康檢查

```python
from src.utils.health_checker import HealthChecker

checker = HealthChecker()

# 添加自定義檢查
async def check_custom_service():
    try:
        # 檢查服務狀態
        return {'status': 'healthy'}
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}

checker.add_check('custom_service', check_custom_service)
```

## 安全最佳實踐

### 1. 輸入驗證

```python
from marshmallow import Schema, fields, validate

class AnalysisRequestSchema(Schema):
    content = fields.Str(required=True, validate=validate.Length(min=1, max=20*1024*1024))
    log_type = fields.Str(required=True, validate=validate.OneOf(['anr', 'tombstone']))
    mode = fields.Str(validate=validate.OneOf(['quick', 'intelligent', 'large_file', 'max_token']))

# 使用 schema 驗證
schema = AnalysisRequestSchema()
data = schema.load(request.json)
```

### 2. 速率限制

```python
from src.api.middleware.rate_limit import rate_limit

@app.route('/api/analyze')
@rate_limit(requests_per_minute=10)
async def analyze():
    pass
```

### 3. 敏感資料處理

```python
import re

def sanitize_log(content: str) -> str:
    """移除敏感資訊"""
    # 移除 email
    content = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL]', content)
    
    # 移除 IP 地址
    content = re.sub(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', '[IP]', content)
    
    # 移除 API 金鑰模式
    content = re.sub(r'[a-zA-Z0-9]{32,}', '[KEY]', content)
    
    return content
```

## 貢獻指南

### 1. Fork 和 Clone

```bash
# Fork 專案到您的 GitHub
# Clone 您的 fork
git clone https://github.com/YOUR_USERNAME/anr-tombstone-ai-analyzer.git
cd anr-tombstone-ai-analyzer
```

### 2. 創建分支

```bash
# 創建功能分支
git checkout -b feature/your-feature-name

# 或修復分支
git checkout -b fix/issue-description
```

### 3. 開發和測試

```bash
# 開發您的功能
# 運行測試
pytest

# 檢查代碼風格
flake8 src/
black src/ --check
```

### 4. 提交變更

```bash
# 提交變更
git add .
git commit -m "feat: add new analysis mode"

# 推送到您的 fork
git push origin feature/your-feature-name
```

### 5. 創建 Pull Request

1. 在 GitHub 上創建 PR
2. 填寫 PR 模板
3. 等待代碼審查
4. 根據反饋修改
5. 合併到主分支

## 版本發布

### 1. 版本號規則

使用語義化版本：`MAJOR.MINOR.PATCH`

- MAJOR: 不兼容的 API 變更
- MINOR: 向後兼容的功能新增
- PATCH: 向後兼容的錯誤修復

### 2. 發布流程

```bash
# 更新版本號
bumpversion minor  # 或 major, patch

# 創建標籤
git tag -a v1.1.0 -m "Release version 1.1.0"

# 推送標籤
git push origin v1.1.0

# 構建和發布
python setup.py sdist bdist_wheel
twine upload dist/*
```

## 資源連結

### 文檔
- [API 文檔](api-reference.md)
- [架構設計](architecture/system-design.md)
- [配置指南](configuration.md)

### 工具
- [Postman Collection](https://www.postman.com/anr-analyzer)
- [OpenAPI Spec](https://api.anr-analyzer.com/openapi.json)
- [GraphQL Playground](https://api.anr-analyzer.com/graphql)

### 社群
- [GitHub Discussions](https://github.com/your-org/anr-analyzer/discussions)
- [Slack Channel](https://anr-analyzer.slack.com)
- [Stack Overflow Tag](https://stackoverflow.com/questions/tagged/anr-analyzer)