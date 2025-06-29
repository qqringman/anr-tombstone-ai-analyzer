# 配置說明

本文檔詳細說明 ANR/Tombstone AI 分析系統的所有配置選項。

## 配置檔案概覽

系統使用多層配置系統，優先級從高到低：

1. 環境變數
2. `.env` 檔案
3. `config.yaml` 檔案
4. 預設值

## 環境變數配置 (.env)

### API 金鑰配置

```bash
# Anthropic API 金鑰（必填其一）
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxx

# OpenAI API 金鑰（必填其一）
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
```

### 資料庫配置

```bash
# 資料庫密碼
DB_PASSWORD=secure_password_here

# 資料庫連接 URL
# SQLite (開發環境)
DATABASE_URL=sqlite:///data/analysis.db

# PostgreSQL (生產環境)
DATABASE_URL=postgresql://analyzer:secure_password_here@localhost:5432/ai_analyzer

# MySQL (替代選項)
DATABASE_URL=mysql://analyzer:secure_password_here@localhost:3306/ai_analyzer
```

### Redis 配置

```bash
# Redis 密碼（如有設定）
REDIS_PASSWORD=redis_password_here

# Redis 連接 URL
REDIS_URL=redis://:redis_password_here@localhost:6379/0
```

### 安全性配置

```bash
# 應用密鑰（用於會話加密）
SECRET_KEY=your-secret-key-generate-with-openssl-rand-hex-32

# JWT 密鑰（用於 API 認證）
JWT_SECRET_KEY=your-jwt-secret-key

# API Token（可選，用於簡單認證）
API_TOKEN=your-api-token

# 管理員 Token（用於管理功能）
ADMIN_TOKEN=your-admin-token
```

### 應用配置

```bash
# 環境設定：development, staging, production
ENVIRONMENT=development

# 是否開啟調試模式
DEBUG=False

# 日誌級別：DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# API 服務設定
API_HOST=0.0.0.0
API_PORT=5000
```

### 檔案上傳配置

```bash
# 最大上傳檔案大小（位元組）
MAX_CONTENT_LENGTH=20971520  # 20MB

# 允許的檔案副檔名
ALLOWED_EXTENSIONS=txt,log
```

### AI 配置

```bash
# 預設 AI 提供者：anthropic, openai
DEFAULT_AI_PROVIDER=anthropic

# 預設分析模式：quick, intelligent, large_file, max_token
DEFAULT_ANALYSIS_MODE=intelligent

# 最大並行分析數
MAX_CONCURRENT_ANALYSES=5
```

### 成本控制

```bash
# 預設預算限制（美元）
DEFAULT_BUDGET_USD=10.0

# 預算警告閾值（0-1）
BUDGET_WARNING_THRESHOLD=0.8
```

### 速率限制

```bash
# 是否啟用速率限制
RATE_LIMIT_ENABLED=true

# 每分鐘請求數限制
RATE_LIMIT_PER_MINUTE=60

# 每小時請求數限制
RATE_LIMIT_PER_HOUR=1000
```

## YAML 配置檔案 (config.yaml)

### 系統配置

```yaml
system:
  name: "ANR/Tombstone AI Analyzer"
  version: "1.0.0"
  description: "AI-powered Android crash log analysis system"
```

### API 服務配置

```yaml
api:
  host: "0.0.0.0"
  port: 5000
  workers: 4
  timeout: 300  # 秒
  cors:
    enabled: true
    origins: ["*"]
    methods: ["GET", "POST", "OPTIONS"]
```

### AI 提供者配置

```yaml
providers:
  anthropic:
    enabled: true
    default_model: "claude-sonnet-4-20250514"
    models:
      - name: "claude-3-5-haiku-20241022"
        tier: 2
        max_tokens: 8192
      - name: "claude-3-5-sonnet-20241022"
        tier: 3
        max_tokens: 8192
      - name: "claude-sonnet-4-20250514"
        tier: 3
        max_tokens: 16000
      - name: "claude-opus-4-20250514"
        tier: 4
        max_tokens: 32000
    
  openai:
    enabled: true
    default_model: "gpt-4o"
    models:
      - name: "gpt-4o-mini"
        tier: 2
        max_tokens: 16384
      - name: "gpt-4o"
        tier: 3
        max_tokens: 16384
      - name: "gpt-4-turbo"
        tier: 4
        max_tokens: 4096
```

### 分析模式配置

```yaml
analysis_modes:
  quick:
    description: "快速分析，找出關鍵問題"
    chunk_size: 50000
    max_tokens: 2000
    timeout: 120
    model_overrides:
      anthropic: "claude-3-5-haiku-20241022"
      openai: "gpt-4o-mini"
  
  intelligent:
    description: "智能分析，平衡速度與深度"
    chunk_size: 150000
    max_tokens: 8000
    timeout: 300
    model_overrides:
      anthropic: "claude-sonnet-4-20250514"
      openai: "gpt-4o"
  
  large_file:
    description: "大檔案分析，優化處理效率"
    chunk_size: 200000
    max_tokens: 8000
    timeout: 600
    parallel_chunks: 3
  
  max_token:
    description: "深度分析，最詳細的報告"
    chunk_size: 180000
    max_tokens: 16000
    timeout: 900
    model_overrides:
      anthropic: "claude-opus-4-20250514"
      openai: "gpt-4-turbo"
```

### 系統限制

```yaml
limits:
  max_file_size_mb: 20          # 最大檔案大小
  max_tokens_per_request: 200000 # 每個請求最大 tokens
  default_budget_usd: 10.0       # 預設預算
  request_timeout_seconds: 300   # 請求超時
  max_concurrent_analyses: 5     # 最大並行分析數
  max_queue_size: 100           # 任務佇列大小
  
  rate_limits:
    per_minute: 60
    per_hour: 1000
    burst_size: 10
```

### 快取配置

```yaml
cache:
  enabled: true
  backend: "disk"  # disk, redis, memory
  ttl_hours: 24
  max_memory_items: 100
  directory: ".cache/ai_analysis"
  
  redis:
    enabled: false
    ttl_seconds: 86400
    key_prefix: "anr_analyzer:"
```

### 日誌配置

```yaml
logging:
  level: "INFO"
  format: "json"  # json, text
  directory: "logs"
  max_file_size_mb: 10
  backup_count: 5
  
  handlers:
    console:
      enabled: true
      level: "INFO"
    
    file:
      enabled: true
      level: "DEBUG"
      filename: "app.log"
    
    error_file:
      enabled: true
      level: "ERROR"
      filename: "error.log"
```

### 資料庫配置

```yaml
database:
  pool_size: 5
  max_overflow: 10
  pool_timeout: 30
  echo: false  # SQL 日誌
  
  migrations:
    auto_upgrade: false
    directory: "migrations"
```

### 監控配置

```yaml
monitoring:
  enabled: true
  health_check_interval: 300  # 秒
  
  metrics:
    enabled: true
    port: 9090
    path: "/metrics"
  
  sentry:
    enabled: false
    dsn: ""
    environment: "production"
    traces_sample_rate: 0.1
  
  alerts:
    enabled: false
    webhooks:
      - url: "https://hooks.slack.com/services/xxx"
        events: ["error", "budget_exceeded"]
```

## 模型偏好設定

```yaml
model_preferences:
  default_provider: "anthropic"
  fallback_provider: "openai"
  
  # 特定場景的模型選擇
  mode_overrides:
    quick:
      anthropic: "claude-3-5-haiku-20241022"
      openai: "gpt-4o-mini"
    
    intelligent:
      anthropic: "claude-sonnet-4-20250514"
      openai: "gpt-4o"
    
    large_file:
      anthropic: "claude-sonnet-4-20250514"
      openai: "gpt-4o"
    
    max_token:
      anthropic: "claude-opus-4-20250514"
      openai: "gpt-4-turbo"
  
  # 成本優化設定
  cost_optimization:
    enabled: true
    prefer_cheaper_models: true
    budget_threshold: 5.0  # 切換到便宜模型的預算閾值
```

## 進階配置

### 並行處理配置

```yaml
parallel_processing:
  enabled: true
  max_workers: 5
  chunk_processor:
    batch_size: 10
    timeout: 300
```

### 任務佇列配置

```yaml
task_queue:
  backend: "memory"  # memory, redis, database
  max_size: 100
  priority_levels: 5
  
  workers:
    count: 3
    poll_interval: 1  # 秒
```

### 安全性配置

```yaml
security:
  cors:
    enabled: true
    origins: ["http://localhost:*", "https://*.yourdomain.com"]
    credentials: true
  
  csrf:
    enabled: true
    token_length: 32
  
  content_security_policy:
    enabled: true
    directives:
      default-src: ["'self'"]
      script-src: ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"]
      style-src: ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"]
```

## 配置驗證

系統啟動時會自動驗證配置，您也可以手動驗證：

```bash
# 驗證配置
python -m src.config.validate

# 或使用健康檢查腳本
python scripts/health_check.py --config-only
```

## 配置最佳實踐

### 開發環境

```yaml
# config.development.yaml
environment: development
debug: true
logging:
  level: DEBUG
database:
  echo: true
cache:
  enabled: false
```

### 生產環境

```yaml
# config.production.yaml
environment: production
debug: false
logging:
  level: WARNING
database:
  echo: false
cache:
  enabled: true
  backend: redis
monitoring:
  enabled: true
  sentry:
    enabled: true
```

### 安全建議

1. **API 金鑰管理**
   - 永遠不要將 API 金鑰提交到版本控制
   - 使用環境變數或密鑰管理服務
   - 定期輪換金鑰

2. **資料庫安全**
   - 使用強密碼
   - 限制資料庫訪問 IP
   - 定期備份

3. **應用安全**
   - 在生產環境關閉 DEBUG
   - 使用 HTTPS
   - 設定適當的 CORS 政策

## 配置範例

### 最小配置（開發環境）

`.env`:
```bash
ANTHROPIC_API_KEY=your_key
ENVIRONMENT=development
```

### 完整配置（生產環境）

`.env`:
```bash
# API Keys
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
OPENAI_API_KEY=sk-proj-xxxxx

# Database
DATABASE_URL=postgresql://analyzer:password@db:5432/ai_analyzer

# Redis
REDIS_URL=redis://:password@redis:6379/0

# Security
SECRET_KEY=generated-secret-key
JWT_SECRET_KEY=generated-jwt-key

# Environment
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=WARNING
```

`config.yaml`:
```yaml
system:
  name: "ANR/Tombstone AI Analyzer"
  version: "1.0.0"

api:
  host: "0.0.0.0"
  port: 5000
  workers: 8

cache:
  enabled: true
  backend: "redis"

monitoring:
  enabled: true
  sentry:
    enabled: true
    dsn: "your-sentry-dsn"
```

## 故障排除

### 配置載入問題
- 檢查檔案路徑和權限
- 驗證 YAML 語法
- 查看啟動日誌

### 環境變數問題
- 確保 `.env` 檔案在專案根目錄
- 檢查變數名稱拼寫
- 使用 `python -m src.config.debug` 查看載入的配置