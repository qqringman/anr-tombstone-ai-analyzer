/**
 * ANR/Tombstone AI 分析系統 - 主要 JavaScript
 */

// Application State
const AppState = {
    currentFile: null,
    analysisId: null,
    eventSource: null,
    analysisResults: {
        content: '',
        raw: '',
        stats: {},
        startTime: null,
        endTime: null
    },
    isAnalyzing: false,
    settings: {
        autoDetectLogType: true,
        saveHistory: true,
        maxHistoryItems: 10
    }
};

// Initialize Application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Load settings
    loadSettings();
    
    // Setup components
    FileHandler.init();
    AnalysisController.init();
    UIController.init();
    StatusMonitor.init();
    
    // Check system status
    checkSystemHealth();
    
    // Load analysis history
    loadAnalysisHistory();
    
    // Setup keyboard shortcuts
    setupKeyboardShortcuts();
}

// File Handler Module
const FileHandler = {
    init() {
        this.setupDropZone();
        this.setupFileInput();
    },

    setupDropZone() {
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');

        dropZone.addEventListener('click', () => fileInput.click());
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, this.preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.add('drag-over');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => {
                dropZone.classList.remove('drag-over');
            });
        });

        dropZone.addEventListener('drop', this.handleDrop);
    },

    setupFileInput() {
        const fileInput = document.getElementById('fileInput');
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.processFile(e.target.files[0]);
            }
        });
    },

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    },

    handleDrop(e) {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            FileHandler.processFile(files[0]);
        }
    },

    async processFile(file) {
        // Validate file
        const validation = this.validateFile(file);
        if (!validation.valid) {
            UIController.showMessage(validation.message, 'error');
            return;
        }

        AppState.currentFile = file;
        
        // Update UI
        this.updateFileInfo(file);
        
        // Auto-detect log type if enabled
        if (AppState.settings.autoDetectLogType) {
            await this.detectLogType(file);
        }
        
        // Estimate analysis cost
        await CostEstimator.estimate(file);
        
        // Enable analysis button
        UIController.enableAnalysis();
    },

    validateFile(file) {
        const maxSize = 20 * 1024 * 1024; // 20MB
        const allowedTypes = ['.txt', '.log'];
        const extension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

        if (!allowedTypes.includes(extension)) {
            return { valid: false, message: '請上傳 .txt 或 .log 檔案' };
        }

        if (file.size > maxSize) {
            return { valid: false, message: '檔案大小不能超過 20MB' };
        }

        return { valid: true };
    },

    updateFileInfo(file) {
        document.getElementById('fileName').textContent = file.name;
        document.getElementById('fileSize').textContent = Utils.formatFileSize(file.size);
        document.getElementById('estimatedTokens').textContent = 
            Utils.estimateTokens(file.size).toLocaleString();
        document.getElementById('fileInfo').classList.add('active');
    },

    async detectLogType(file) {
        const reader = new FileReader();
        const content = await this.readFileContent(file, 2048); // Read first 2KB
        
        const patterns = {
            anr: [
                /DALVIK THREADS/i,
                /----- pid \d+ at/,
                /Cmd line:/,
                /"main" prio=\d+ tid=\d+/,
                /at android\./
            ],
            tombstone: [
                /\*\*\* \*\*\* \*\*\*/,
                /Build fingerprint:/,
                /signal \d+ \(SIG\w+\)/,
                /backtrace:/,
                /Tombstone written to:/
            ]
        };

        let anrScore = 0;
        let tombstoneScore = 0;

        patterns.anr.forEach(pattern => {
            if (pattern.test(content)) anrScore++;
        });

        patterns.tombstone.forEach(pattern => {
            if (pattern.test(content)) tombstoneScore++;
        });

        if (anrScore > tombstoneScore && anrScore >= 2) {
            document.querySelector('input[value="anr"]').checked = true;
            document.getElementById('fileType').textContent = 'ANR Log (自動檢測)';
        } else if (tombstoneScore > anrScore && tombstoneScore >= 2) {
            document.querySelector('input[value="tombstone"]').checked = true;
            document.getElementById('fileType').textContent = 'Tombstone Log (自動檢測)';
        } else {
            document.getElementById('fileType').textContent = '未知類型';
        }
    },

    readFileContent(file, bytes = null) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = reject;
            
            if (bytes) {
                reader.readAsText(file.slice(0, bytes));
            } else {
                reader.readAsText(file);
            }
        });
    }
};

// Analysis Controller Module
const AnalysisController = {
    init() {
        document.getElementById('analyzeBtn').addEventListener('click', () => this.startAnalysis());
        document.getElementById('cancelBtn').addEventListener('click', () => this.cancelAnalysis());
        document.getElementById('clearBtn').addEventListener('click', () => this.clearAll());
        
        // Listen to option changes
        ['logType', 'analysisMode', 'provider'].forEach(name => {
            document.querySelectorAll(`input[name="${name}"]`).forEach(radio => {
                radio.addEventListener('change', () => CostEstimator.estimate(AppState.currentFile));
            });
        });
    },

    async startAnalysis() {
        if (!AppState.currentFile || AppState.isAnalyzing) return;

        const options = this.getAnalysisOptions();
        const content = await FileHandler.readFileContent(AppState.currentFile);

        AppState.isAnalyzing = true;
        AppState.analysisResults = {
            content: '',
            raw: '',
            stats: {},
            startTime: new Date(),
            endTime: null
        };

        UIController.setAnalyzing(true);
        
        try {
            const result = await ApiClient.analyzeWithCancellation({
                content,
                ...options
            });

            if (result.success) {
                AppState.analysisId = result.analysisId;
                this.connectSSE(result.streamUrl);
            }
        } catch (error) {
            UIController.showMessage(`錯誤: ${error.message}`, 'error');
            this.stopAnalysis();
        }
    },

    getAnalysisOptions() {
        return {
            log_type: document.querySelector('input[name="logType"]:checked').value,
            mode: document.querySelector('input[name="analysisMode"]:checked').value,
            provider: document.querySelector('input[name="provider"]:checked').value
        };
    },

    connectSSE(url) {
        AppState.eventSource = new EventSource(url);
        
        AppState.eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleSSEMessage(data);
        };

        AppState.eventSource.onerror = (error) => {
            console.error('SSE error:', error);
            UIController.showMessage('連接錯誤，請重試', 'error');
            this.stopAnalysis();
        };
    },

    handleSSEMessage(data) {
        switch (data.type) {
            case 'start':
                UIController.updateAnalysisId(data.analysis_id);
                StatusMonitor.addLog('開始分析', 'info');
                break;
                
            case 'content':
                this.appendContent(data.content);
                break;
                
            case 'progress':
                UIController.updateProgress(data.progress);
                break;
                
            case 'feedback':
                UIController.handleFeedback(data);
                break;
                
            case 'complete':
                this.completeAnalysis();
                break;
                
            case 'cancelled':
                UIController.showMessage('分析已取消', 'warning');
                this.stopAnalysis();
                break;
                
            case 'error':
                UIController.showMessage(`錯誤: ${data.error}`, 'error');
                this.stopAnalysis();
                break;
        }
    },

    appendContent(content) {
        AppState.analysisResults.content += content;
        AppState.analysisResults.raw += content;
        UIController.updateResults();
    },

    async cancelAnalysis() {
        if (!AppState.analysisId || !AppState.isAnalyzing) return;

        try {
            await ApiClient.cancelAnalysis(AppState.analysisId);
            UIController.showMessage('正在取消分析...', 'info');
        } catch (error) {
            console.error('Cancel error:', error);
        }
    },

    completeAnalysis() {
        AppState.analysisResults.endTime = new Date();
        AppState.isAnalyzing = false;
        
        UIController.showMessage('分析完成！', 'success');
        this.stopAnalysis();
        UIController.showResults();
        
        // Save to history
        if (AppState.settings.saveHistory) {
            this.saveToHistory();
        }
        
        // Generate statistics
        this.generateStatistics();
    },

    stopAnalysis() {
        if (AppState.eventSource) {
            AppState.eventSource.close();
            AppState.eventSource = null;
        }
        
        AppState.isAnalyzing = false;
        UIController.setAnalyzing(false);
    },

    clearAll() {
        AppState.currentFile = null;
        AppState.analysisId = null;
        AppState.analysisResults = {
            content: '',
            raw: '',
            stats: {},
            startTime: null,
            endTime: null
        };
        
        UIController.clearAll();
    },

    saveToHistory() {
        const history = JSON.parse(localStorage.getItem('analysisHistory') || '[]');
        
        history.unshift({
            id: AppState.analysisId,
            fileName: AppState.currentFile.name,
            fileSize: AppState.currentFile.size,
            logType: document.querySelector('input[name="logType"]:checked').value,
            mode: document.querySelector('input[name="analysisMode"]:checked').value,
            provider: document.querySelector('input[name="provider"]:checked').value,
            startTime: AppState.analysisResults.startTime,
            endTime: AppState.analysisResults.endTime,
            timestamp: new Date().toISOString()
        });
        
        // Keep only recent items
        if (history.length > AppState.settings.maxHistoryItems) {
            history.length = AppState.settings.maxHistoryItems;
        }
        
        localStorage.setItem('analysisHistory', JSON.stringify(history));
    },

    generateStatistics() {
        const stats = {
            totalTokens: parseInt(document.getElementById('inputTokens').textContent) + 
                        parseInt(document.getElementById('outputTokens').textContent),
            duration: AppState.analysisResults.endTime - AppState.analysisResults.startTime,
            contentLength: AppState.analysisResults.content.length
        };
        
        AppState.analysisResults.stats = stats;
        UIController.updateStatistics(stats);
    }
};

// Cost Estimator Module
const CostEstimator = {
    async estimate(file) {
        if (!file) return;

        const mode = document.querySelector('input[name="analysisMode"]:checked').value;
        const provider = document.querySelector('input[name="provider"]:checked').value;
        
        try {
            const result = await ApiClient.estimateCost({
                file_size_kb: file.size / 1024,
                mode: mode,
                provider: provider
            });

            this.updateDisplay(result);
        } catch (error) {
            console.error('Cost estimation error:', error);
        }
    },

    updateDisplay(data) {
        if (data.cost_estimates && data.cost_estimates.length > 0) {
            const estimate = data.cost_estimates[0];
            
            document.getElementById('estimatedCost').textContent = 
                `$${estimate.total_cost.toFixed(2)}`;
            document.getElementById('estimatedTime').textContent = 
                `${estimate.analysis_time_minutes.toFixed(1)} 分鐘`;
        }

        document.getElementById('recommendedMode').textContent = 
            data.recommended_mode || '-';
        
        document.getElementById('costSection').classList.add('active');
    }
};

// Status Monitor Module
const StatusMonitor = {
    init() {
        this.checkInterval = setInterval(() => this.checkHealth(), 30000);
        this.checkHealth();
    },

    async checkHealth() {
        try {
            const health = await ApiClient.getHealth();
            this.updateHealthStatus(health);
        } catch (error) {
            this.updateHealthStatus({ status: 'error' });
        }
    },

    updateHealthStatus(health) {
        const indicator = document.getElementById('healthIndicator');
        if (indicator) {
            indicator.className = `health-indicator ${health.status}`;
            indicator.title = `系統狀態: ${health.status}`;
        }
    },

    addLog(message, type = 'info') {
        const log = document.getElementById('statusLog');
        const entry = document.createElement('div');
        entry.className = 'status-log-entry';
        
        const time = new Date().toLocaleTimeString();
        entry.innerHTML = `
            <span class="status-log-time">${time}</span>
            <span class="status-log-type ${type}">[${type.toUpperCase()}]</span>
            <span class="status-log-message">${message}</span>
        `;
        
        log.appendChild(entry);
        log.scrollTop = log.scrollHeight;
        
        // Show status panel
        document.getElementById('statusPanel').classList.add('active');
    }
};

// Settings Management
function loadSettings() {
    const saved = localStorage.getItem('appSettings');
    if (saved) {
        AppState.settings = { ...AppState.settings, ...JSON.parse(saved) };
    }
}

function saveSettings() {
    localStorage.setItem('appSettings', JSON.stringify(AppState.settings));
}

// Analysis History
function loadAnalysisHistory() {
    const history = JSON.parse(localStorage.getItem('analysisHistory') || '[]');
    
    if (history.length > 0) {
        // Could populate a history dropdown or panel
        console.log(`Loaded ${history.length} history items`);
    }
}

// Keyboard Shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + Enter to start analysis
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            if (!AppState.isAnalyzing && AppState.currentFile) {
                AnalysisController.startAnalysis();
            }
        }
        
        // Escape to cancel
        if (e.key === 'Escape' && AppState.isAnalyzing) {
            AnalysisController.cancelAnalysis();
        }
        
        // Ctrl/Cmd + N to clear
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            AnalysisController.clearAll();
        }
    });
}

// System Health Check
async function checkSystemHealth() {
    try {
        const health = await ApiClient.getHealth();
        
        if (health.status === 'healthy') {
            StatusMonitor.addLog('系統狀態正常', 'info');
            
            // Check available providers
            if (health.checks && health.checks.ai_providers) {
                const providers = health.checks.ai_providers;
                StatusMonitor.addLog(`可用 AI 提供者: ${providers.join(', ')}`, 'info');
            }
        } else {
            StatusMonitor.addLog('系統狀態異常', 'warning');
        }
    } catch (error) {
        StatusMonitor.addLog('無法連接到伺服器', 'error');
        UIController.showMessage('無法連接到伺服器，請檢查網路連接', 'error');
    }
}

// Export for use in other modules
window.AppState = AppState;
window.FileHandler = FileHandler;
window.AnalysisController = AnalysisController;
window.CostEstimator = CostEstimator;
window.StatusMonitor = StatusMonitor;