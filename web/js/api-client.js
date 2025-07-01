/**
 * API Client for ANR/Tombstone AI Analysis System
 */

const ApiClient = {
    baseUrl: '/api',
    timeout: 30000,
    
    // Configure headers
    getHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };
        
        // Add auth token if available
        const token = localStorage.getItem('authToken');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        
        // Add session token if available
        const sessionToken = localStorage.getItem('sessionToken');
        if (sessionToken) {
            headers['X-Session-Token'] = sessionToken;
        }
        
        return headers;
    },

    // Generic request method
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            ...options,
            headers: {
                ...this.getHeaders(),
                ...options.headers
            }
        };

        // Add timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);
        config.signal = controller.signal;

        try {
            const response = await fetch(url, config);
            clearTimeout(timeoutId);

            // Handle response
            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.message || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                throw new Error('Request timeout');
            }
            
            throw error;
        }
    },

    // Health check
    async getHealth() {
        return this.request('/health');
    },

    // Get detailed health
    async getDetailedHealth() {
        return this.request('/health/detailed');
    },

    // Basic analysis (synchronous)
    async analyze(params) {
        return this.request('/ai/analyze-with-ai', {
            method: 'POST',
            body: JSON.stringify(params)
        });
    },

    // Analysis with cancellation support
    async analyzeWithCancellation(params) {
        const response = await fetch(`${this.baseUrl}/ai/analyze-with-cancellation`, {
            method: 'POST',
            headers: this.getHeaders(),
            body: JSON.stringify(params)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        // Return SSE URL for streaming
        return {
            success: true,
            analysisId: response.headers.get('X-Analysis-ID') || generateAnalysisId(),
            streamUrl: response.url
        };
    },

    // Cancel analysis
    async cancelAnalysis(analysisId, reason = 'user_cancelled') {
        return this.request(`/ai/cancel-analysis/${analysisId}`, {
            method: 'POST',
            body: JSON.stringify({ reason })
        });
    },

    // Estimate cost
    async estimateCost(params) {
        return this.request('/ai/estimate-analysis-cost', {
            method: 'POST',
            body: JSON.stringify(params)
        });
    },

    // Check file size
    async checkFileSize(fileSize) {
        return this.request('/ai/check-file-size', {
            method: 'POST',
            body: JSON.stringify({ file_size: fileSize })
        });
    },

    // Get analysis status
    async getAnalysisStatus(analysisId) {
        return this.request(`/ai/analysis-status/${analysisId}`);
    },

    // Get analysis result
    async getAnalysisResult(analysisId) {
        return this.request(`/ai/analysis-result/${analysisId}`);
    },

    // Get usage statistics
    async getUsageStats(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/stats/usage${queryString ? `?${queryString}` : ''}`);
    },

    // Get cost statistics
    async getCostStats(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/stats/cost${queryString ? `?${queryString}` : ''}`);
    },

    // Create session
    async createSession() {
        const response = await this.request('/auth/session', {
            method: 'POST',
            body: JSON.stringify({
                user_agent: navigator.userAgent,
                timestamp: new Date().toISOString()
            })
        });

        if (response.session_token) {
            localStorage.setItem('sessionToken', response.session_token);
        }

        return response;
    },

    // SSE Helper
    createEventSource(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = `${this.baseUrl}${endpoint}${queryString ? `?${queryString}` : ''}`;
        
        const eventSource = new EventSource(url, {
            withCredentials: true
        });

        // Add auth headers if supported (not standard SSE)
        const token = localStorage.getItem('authToken');
        if (token && eventSource.addEventListener) {
            // Custom implementation for auth
            eventSource.addEventListener('open', () => {
                console.log('SSE connection opened');
            });
        }

        return eventSource;
    },

    // Upload file (for future use)
    async uploadFile(file, onProgress) {
        const formData = new FormData();
        formData.append('file', file);

        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();

            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable && onProgress) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    onProgress(percentComplete);
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    resolve(JSON.parse(xhr.responseText));
                } else {
                    reject(new Error(`Upload failed: ${xhr.status}`));
                }
            });

            xhr.addEventListener('error', () => {
                reject(new Error('Upload failed'));
            });

            xhr.open('POST', `${this.baseUrl}/upload`);
            
            // Add headers
            const headers = this.getHeaders();
            delete headers['Content-Type']; // Let browser set it for FormData
            
            for (const [key, value] of Object.entries(headers)) {
                xhr.setRequestHeader(key, value);
            }

            xhr.send(formData);
        });
    },

    // Batch analysis
    async batchAnalyze(files, options) {
        const analyses = files.map(file => ({
            file_name: file.name,
            file_size: file.size,
            ...options
        }));

        return this.request('/ai/batch-analyze', {
            method: 'POST',
            body: JSON.stringify({ analyses })
        });
    },

    // Get available models
    async getAvailableModels(provider) {
        return this.request(`/ai/models/${provider}`);
    },

    // Get prompts
    async getPrompts(logType, mode) {
        return this.request(`/prompts/${logType}/${mode}`);
    },

    // Update prompt
    async updatePrompt(logType, mode, prompt) {
        return this.request(`/prompts/${logType}/${mode}`, {
            method: 'PUT',
            body: JSON.stringify({ prompt })
        });
    },

    // Error handling helper
    handleError(error) {
        console.error('API Error:', error);
        
        // Check for specific error types
        if (error.message.includes('timeout')) {
            return { error: '請求超時，請重試' };
        }
        
        if (error.message.includes('401')) {
            // Handle authentication error
            localStorage.removeItem('authToken');
            localStorage.removeItem('sessionToken');
            return { error: '認證失敗，請重新登入' };
        }
        
        if (error.message.includes('429')) {
            return { error: '請求過於頻繁，請稍後再試' };
        }
        
        return { error: error.message || '未知錯誤' };
    },

    // 獲取速率限制資訊
    async getRateLimits(provider, tier = null, model = null) {
        const params = new URLSearchParams();
        if (tier) params.append('tier', tier);
        if (model) params.append('model', model);
        
        return this.request(`/ai/rate-limits/${provider}?${params}`);
    },
    
    // 建議最佳層級
    async suggestTier(params) {
        return this.request('/ai/suggest-tier', {
            method: 'POST',
            body: JSON.stringify(params)
        });
    }    
};

// Utility function to generate analysis ID
function generateAnalysisId() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// Export for use
window.ApiClient = ApiClient;