# 部署指南

本指南詳細說明如何將 ANR/Tombstone AI 分析系統部署到各種環境。

## 部署選項概覽

- **Docker 部署**：最簡單快速的部署方式
- **Kubernetes 部署**：適合大規模生產環境
- **雲端部署**：AWS、GCP、Azure 等雲平台
- **傳統部署**：直接在伺服器上部署

## 前置準備

### 系統需求

**最低配置（開發/測試）**：
- CPU: 2 核心
- 記憶體: 4GB
- 儲存: 10GB SSD
- 網路: 穩定的網際網路連接

**建議配置（生產環境）**：
- CPU: 4+ 核心
- 記憶體: 8GB+
- 儲存: 50GB+ SSD
- 網路: 高速網際網路連接

### 必要軟體

- Docker 20.10+ 和 Docker Compose 2.0+
- Python 3.11+
- PostgreSQL 15+ (生產環境)
- Redis 7+ (生產環境)
- Nginx (反向代理)

## Docker 部署

### 1. 單機 Docker 部署

#### 準備配置檔案

```bash
# 克隆專案
git clone https://github.com/your-org/anr-tombstone-ai-analyzer.git
cd anr-tombstone-ai-analyzer

# 創建環境變數檔案
cp .env.example .env.production

# 編輯環境變數
nano .env.production
```

必要的環境變數：
```bash
# API Keys
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
OPENAI_API_KEY=sk-proj-xxxxx

# Database
DATABASE_URL=postgresql://analyzer:secure_password@db:5432/ai_analyzer

# Redis
REDIS_URL=redis://:redis_password@redis:6379/0

# Security
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)
API_TOKEN=$(openssl rand -hex 32)

# Environment
ENVIRONMENT=production
DEBUG=False
```

#### 構建和啟動

```bash
# 構建映像
docker build -t anr-analyzer:latest .

# 使用 docker-compose
docker-compose -f docker-compose.prod.yml up -d

# 檢查狀態
docker-compose ps
docker-compose logs -f
```

### 2. Docker Compose 生產配置

創建 `docker-compose.prod.yml`：

```yaml
version: '3.8'

services:
  api:
    image: anr-analyzer:latest
    container_name: anr-analyzer-api
    env_file: .env.production
    ports:
      - "127.0.0.1:5000:5000"
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
      - ./.cache:/app/.cache
    depends_on:
      - db
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  web:
    image: nginx:alpine
    container_name: anr-analyzer-web
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./web:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    restart: unless-stopped

  db:
    image: postgres:15-alpine
    container_name: anr-analyzer-db
    environment:
      POSTGRES_USER: analyzer
      POSTGRES_PASSWORD: secure_password
      POSTGRES_DB: ai_analyzer
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: anr-analyzer-redis
    command: redis-server --requirepass redis_password
    volumes:
      - redis_data:/data
    restart: unless-stopped

  backup:
    image: postgres:15-alpine
    container_name: anr-analyzer-backup
    env_file: .env.production
    volumes:
      - ./backups:/backups
    command: |
      sh -c 'while true; do
        PGPASSWORD=$$POSTGRES_PASSWORD pg_dump -h db -U analyzer ai_analyzer > /backups/backup_$$(date +%Y%m%d_%H%M%S).sql
        find /backups -name "backup_*.sql" -mtime +7 -delete
        sleep 86400
      done'
    depends_on:
      - db
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:

networks:
  default:
    name: anr-analyzer-network
```

### 3. Nginx 配置

創建 `nginx.conf`：

```nginx
upstream api {
    server api:5000;
}

server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval';" always;
    
    # Static files
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }
    
    # API proxy
    location /api/ {
        proxy_pass http://api/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
    
    # File upload size
    client_max_body_size 25M;
    
    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
    gzip_min_length 1000;
}
```

## Kubernetes 部署

### 1. 準備 Kubernetes 資源

創建命名空間：
```bash
kubectl create namespace anr-analyzer
```

### 2. ConfigMap 和 Secret

創建 `k8s/configmap.yaml`：
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: anr-analyzer-config
  namespace: anr-analyzer
data:
  ENVIRONMENT: "production"
  DEBUG: "False"
  LOG_LEVEL: "INFO"
  DATABASE_URL: "postgresql://analyzer:password@postgres-service:5432/ai_analyzer"
  REDIS_URL: "redis://:password@redis-service:6379/0"
```

創建 Secret：
```bash
kubectl create secret generic anr-analyzer-secrets \
  --from-literal=ANTHROPIC_API_KEY=your-key \
  --from-literal=OPENAI_API_KEY=your-key \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32) \
  --from-literal=JWT_SECRET_KEY=$(openssl rand -hex 32) \
  -n anr-analyzer
```

### 3. Deployment 配置

創建 `k8s/deployment.yaml`：
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: anr-analyzer-api
  namespace: anr-analyzer
spec:
  replicas: 3
  selector:
    matchLabels:
      app: anr-analyzer-api
  template:
    metadata:
      labels:
        app: anr-analyzer-api
    spec:
      containers:
      - name: api
        image: anr-analyzer:latest
        ports:
        - containerPort: 5000
        envFrom:
        - configMapRef:
            name: anr-analyzer-config
        - secretRef:
            name: anr-analyzer-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: cache
          mountPath: /app/.cache
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: cache
        emptyDir: {}
      - name: logs
        emptyDir: {}
```

### 4. Service 配置

創建 `k8s/service.yaml`：
```yaml
apiVersion: v1
kind: Service
metadata:
  name: anr-analyzer-service
  namespace: anr-analyzer
spec:
  selector:
    app: anr-analyzer-api
  ports:
  - port: 80
    targetPort: 5000
  type: ClusterIP
```

### 5. Ingress 配置

創建 `k8s/ingress.yaml`：
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: anr-analyzer-ingress
  namespace: anr-analyzer
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - anr-analyzer.yourdomain.com
    secretName: anr-analyzer-tls
  rules:
  - host: anr-analyzer.yourdomain.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: anr-analyzer-service
            port:
              number: 80
      - path: /
        pathType: Prefix
        backend:
          service:
            name: anr-analyzer-web
            port:
              number: 80
```

### 6. 部署到 Kubernetes

```bash
# 應用所有配置
kubectl apply -f k8s/

# 檢查部署狀態
kubectl get all -n anr-analyzer

# 查看日誌
kubectl logs -f deployment/anr-analyzer-api -n anr-analyzer

# 擴展副本
kubectl scale deployment/anr-analyzer-api --replicas=5 -n anr-analyzer
```

## 雲端部署

### AWS 部署

#### 1. 使用 ECS (Elastic Container Service)

創建任務定義：
```json
{
  "family": "anr-analyzer",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "your-ecr-repo/anr-analyzer:latest",
      "portMappings": [
        {
          "containerPort": 5000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "ENVIRONMENT", "value": "production"}
      ],
      "secrets": [
        {
          "name": "ANTHROPIC_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:anr-analyzer"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/anr-analyzer",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### 2. 使用 Elastic Beanstalk

創建 `.ebextensions/01_python.config`：
```yaml
option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: src.api.app:app
  aws:elasticbeanstalk:application:environment:
    ENVIRONMENT: production
    DATABASE_URL: your-rds-endpoint
```

部署命令：
```bash
# 初始化 EB
eb init -p python-3.11 anr-analyzer

# 創建環境
eb create anr-analyzer-prod

# 部署
eb deploy
```

### Google Cloud Platform 部署

#### 1. 使用 Cloud Run

```bash
# 構建並推送到 GCR
gcloud builds submit --tag gcr.io/PROJECT-ID/anr-analyzer

# 部署到 Cloud Run
gcloud run deploy anr-analyzer \
  --image gcr.io/PROJECT-ID/anr-analyzer \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="ENVIRONMENT=production" \
  --set-secrets="ANTHROPIC_API_KEY=anthropic-key:latest"
```

#### 2. 使用 App Engine

創建 `app.yaml`：
```yaml
runtime: python311
entrypoint: gunicorn -b :$PORT src.api.app:app

env_variables:
  ENVIRONMENT: "production"

automatic_scaling:
  target_cpu_utilization: 0.65
  min_instances: 1
  max_instances: 10

resources:
  cpu: 2
  memory_gb: 2.5
  disk_size_gb: 10
```

部署：
```bash
gcloud app deploy
```

### Azure 部署

#### 使用 Container Instances

```bash
# 創建資源組
az group create --name anr-analyzer-rg --location westus2

# 創建容器實例
az container create \
  --resource-group anr-analyzer-rg \
  --name anr-analyzer \
  --image youracr.azurecr.io/anr-analyzer:latest \
  --dns-name-label anr-analyzer \
  --ports 5000 \
  --environment-variables ENVIRONMENT=production \
  --secure-environment-variables ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
```

## 傳統部署

### 1. 系統準備

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3-pip nginx postgresql redis-server supervisor

# CentOS/RHEL
sudo yum install -y python3.11 nginx postgresql redis supervisor
```

### 2. 應用設置

```bash
# 創建用戶
sudo useradd -m -s /bin/bash analyzer

# 創建目錄
sudo mkdir -p /opt/anr-analyzer
sudo chown analyzer:analyzer /opt/anr-analyzer

# 切換用戶
sudo su - analyzer

# 克隆代碼
cd /opt/anr-analyzer
git clone https://github.com/your-org/anr-analyzer.git .

# 創建虛擬環境
python3.11 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# 設置環境變數
cp .env.example .env
nano .env
```

### 3. Supervisor 配置

創建 `/etc/supervisor/conf.d/anr-analyzer.conf`：

```ini
[program:anr-analyzer]
command=/opt/anr-analyzer/venv/bin/gunicorn -w 4 -k gevent --timeout 300 -b 127.0.0.1:5000 src.api.app:app
directory=/opt/anr-analyzer
user=analyzer
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/anr-analyzer/app.log
environment=PATH="/opt/anr-analyzer/venv/bin",ENVIRONMENT="production"
```

### 4. Nginx 配置

創建 `/etc/nginx/sites-available/anr-analyzer`：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        root /opt/anr-analyzer/web;
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE support
        proxy_buffering off;
        proxy_cache off;
    }

    client_max_body_size 25M;
}
```

啟用站點：
```bash
sudo ln -s /etc/nginx/sites-available/anr-analyzer /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 5. 啟動服務

```bash
# 啟動 Supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start anr-analyzer

# 檢查狀態
sudo supervisorctl status
```

## 部署後配置

### 1. SSL 證書設置

使用 Let's Encrypt：
```bash
# 安裝 certbot
sudo apt-get install certbot python3-certbot-nginx

# 獲取證書
sudo certbot --nginx -d your-domain.com

# 自動更新
sudo certbot renew --dry-run
```

### 2. 資料庫優化

PostgreSQL 優化：
```sql
-- 調整連接池
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '256MB';

-- 創建索引
CREATE INDEX idx_analysis_created ON analysis_records(created_at);
CREATE INDEX idx_analysis_user ON analysis_records(user_id);

-- 分區表（大數據量）
CREATE TABLE analysis_records_2025_01 PARTITION OF analysis_records
FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

### 3. 監控設置

#### Prometheus 配置

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'anr-analyzer'
    static_configs:
      - targets: ['localhost:9090']
```

#### Grafana Dashboard

導入預設的 dashboard：
1. 登入 Grafana
2. Import Dashboard
3. 使用 ID: 12345 (假設的 ID)

### 4. 備份策略

自動備份腳本：
```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"

# 備份資料庫
pg_dump ai_analyzer > $BACKUP_DIR/db_$DATE.sql

# 備份檔案
tar -czf $BACKUP_DIR/files_$DATE.tar.gz /opt/anr-analyzer/data

# 上傳到 S3
aws s3 cp $BACKUP_DIR/db_$DATE.sql s3://your-backup-bucket/
aws s3 cp $BACKUP_DIR/files_$DATE.tar.gz s3://your-backup-bucket/

# 清理舊備份
find $BACKUP_DIR -mtime +7 -delete
```

設置 cron job：
```bash
0 2 * * * /opt/anr-analyzer/scripts/backup.sh
```

## 效能優化

### 1. 應用層優化

- 啟用 Redis 快取
- 使用 CDN 加速靜態資源
- 啟用 Gzip 壓縮
- 優化資料庫查詢

### 2. 系統層優化

調整系統參數：
```bash
# /etc/sysctl.conf
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30
```

### 3. 負載均衡

使用 HAProxy：
```
global
    maxconn 4096

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms

backend api_servers
    balance roundrobin
    server api1 10.0.0.1:5000 check
    server api2 10.0.0.2:5000 check
    server api3 10.0.0.3:5000 check
```

## 故障處理

### 常見問題

1. **連接超時**
   - 檢查防火牆規則
   - 確認服務正在運行
   - 檢查 Nginx 配置

2. **記憶體不足**
   - 增加系統記憶體
   - 調整 worker 數量
   - 啟用 swap

3. **磁碟空間不足**
   - 清理日誌檔案
   - 清理快取
   - 增加磁碟空間

### 健康檢查

```bash
# 檢查所有服務
curl http://localhost:5000/api/health

# 檢查資料庫連接
psql -U analyzer -d ai_analyzer -c "SELECT 1"

# 檢查 Redis
redis-cli ping

# 檢查磁碟使用
df -h

# 檢查記憶體
free -m
```

## 安全建議

1. **定期更新**
   - 系統套件
   - Python 依賴
   - Docker 映像

2. **存取控制**
   - 使用防火牆限制端口
   - 設置 IP 白名單
   - 啟用 API 認證

3. **加密通信**
   - 使用 HTTPS
   - 加密資料庫連接
   - 使用 VPN

4. **日誌審計**
   - 記錄所有 API 請求
   - 定期審查日誌
   - 設置異常告警

## 總結

成功部署 ANR/Tombstone AI 分析系統需要：

1. 選擇合適的部署方式
2. 正確配置環境變數
3. 設置適當的資源限制
4. 實施監控和備份
5. 定期維護和更新

遵循本指南，您應該能夠成功部署並運行系統。如遇到問題，請參考[故障排除指南](troubleshooting.md)或聯繫技術支援。