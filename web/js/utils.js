/**
 * Utility functions for ANR/Tombstone AI Analysis System
 */

const Utils = {
    // Format file size
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    // Format duration
    formatDuration(milliseconds) {
        if (milliseconds < 1000) {
            return `${milliseconds}ms`;
        }
        
        const seconds = Math.floor(milliseconds / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes % 60}m`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        } else {
            return `${seconds}s`;
        }
    },

    // Format date
    formatDate(date, format = 'full') {
        if (!(date instanceof Date)) {
            date = new Date(date);
        }
        
        const options = {
            short: { month: 'short', day: 'numeric' },
            medium: { year: 'numeric', month: 'short', day: 'numeric' },
            full: { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' }
        };
        
        return date.toLocaleString('zh-TW', options[format] || options.full);
    },

    // Estimate tokens from text size
    estimateTokens(sizeInBytes) {
        // Rough estimation: 1 token ≈ 2.5 characters for Chinese/English mix
        const characters = sizeInBytes;
        return Math.ceil(characters / 2.5);
    },

    // Debounce function
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Throttle function
    throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    // Copy to clipboard
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            
            try {
                const successful = document.execCommand('copy');
                document.body.removeChild(textArea);
                return successful;
            } catch (err) {
                document.body.removeChild(textArea);
                return false;
            }
        }
    },

    // Download text as file
    downloadTextFile(content, filename) {
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    },

    // Parse markdown to HTML (simple version)
    parseMarkdown(markdown) {
        let html = markdown;
        
        // Headers
        html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
        html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
        
        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        
        // Italic
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        
        // Code blocks
        html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            return `<pre><code class="language-${lang || 'text'}">${escapeHtml(code)}</code></pre>`;
        });
        
        // Inline code
        html = html.replace(/`(.+?)`/g, '<code>$1</code>');
        
        // Links
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
        
        // Lists
        html = html.replace(/^\* (.+)$/gim, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
        
        // Line breaks
        html = html.replace(/\n\n/g, '</p><p>');
        html = '<p>' + html + '</p>';
        
        return html;
    },

    // Escape HTML
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    },

    // Get URL parameters
    getUrlParams() {
        const params = {};
        const searchParams = new URLSearchParams(window.location.search);
        for (const [key, value] of searchParams) {
            params[key] = value;
        }
        return params;
    },

    // Set URL parameter
    setUrlParam(key, value) {
        const url = new URL(window.location);
        url.searchParams.set(key, value);
        window.history.pushState({}, '', url);
    },

    // Remove URL parameter
    removeUrlParam(key) {
        const url = new URL(window.location);
        url.searchParams.delete(key);
        window.history.pushState({}, '', url);
    },

    // Generate unique ID
    generateId(prefix = 'id') {
        return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    },

    // Check if mobile device
    isMobile() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    },

    // Get browser info
    getBrowserInfo() {
        const ua = navigator.userAgent;
        let browser = 'Unknown';
        let version = 'Unknown';
        
        if (ua.indexOf('Firefox') > -1) {
            browser = 'Firefox';
            version = ua.match(/Firefox\/(\d+)/)[1];
        } else if (ua.indexOf('Chrome') > -1) {
            browser = 'Chrome';
            version = ua.match(/Chrome\/(\d+)/)[1];
        } else if (ua.indexOf('Safari') > -1) {
            browser = 'Safari';
            version = ua.match(/Version\/(\d+)/)[1];
        } else if (ua.indexOf('Edge') > -1) {
            browser = 'Edge';
            version = ua.match(/Edge\/(\d+)/)[1];
        }
        
        return { browser, version };
    },

    // Local storage wrapper with JSON support
    storage: {
        get(key, defaultValue = null) {
            try {
                const item = localStorage.getItem(key);
                return item ? JSON.parse(item) : defaultValue;
            } catch (e) {
                return defaultValue;
            }
        },
        
        set(key, value) {
            try {
                localStorage.setItem(key, JSON.stringify(value));
                return true;
            } catch (e) {
                console.error('Storage error:', e);
                return false;
            }
        },
        
        remove(key) {
            localStorage.removeItem(key);
        },
        
        clear() {
            localStorage.clear();
        }
    },

    // Animation helper
    animate(element, animation, duration = 300) {
        return new Promise((resolve) => {
            element.style.animation = `${animation} ${duration}ms`;
            element.addEventListener('animationend', function handler() {
                element.removeEventListener('animationend', handler);
                element.style.animation = '';
                resolve();
            });
        });
    },

    // Smooth scroll to element
    scrollToElement(element, offset = 0) {
        const top = element.getBoundingClientRect().top + window.pageYOffset - offset;
        window.scrollTo({
            top,
            behavior: 'smooth'
        });
    },

    // Format number with commas
    formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    },

    // Calculate percentage
    calculatePercentage(value, total) {
        if (total === 0) return 0;
        return Math.round((value / total) * 100);
    },

    // Validate email
    isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    },

    // Create element with attributes
    createElement(tag, attributes = {}, children = []) {
        const element = document.createElement(tag);
        
        // Set attributes
        for (const [key, value] of Object.entries(attributes)) {
            if (key === 'className') {
                element.className = value;
            } else if (key === 'style' && typeof value === 'object') {
                Object.assign(element.style, value);
            } else if (key.startsWith('on') && typeof value === 'function') {
                element.addEventListener(key.substring(2).toLowerCase(), value);
            } else {
                element.setAttribute(key, value);
            }
        }
        
        // Add children
        children.forEach(child => {
            if (typeof child === 'string') {
                element.appendChild(document.createTextNode(child));
            } else {
                element.appendChild(child);
            }
        });
        
        return element;
    }
};

// UI Controller Module
const UIController = {
    showMessage(message, type = 'info') {
        const container = document.getElementById('statusMessages');
        
        const messageEl = Utils.createElement('div', {
            className: `status-message status-${type}`
        }, [
            Utils.createElement('span', {}, [message])
        ]);
        
        container.appendChild(messageEl);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            Utils.animate(messageEl, 'fadeOut').then(() => {
                messageEl.remove();
            });
        }, 5000);
    },

    updateProgress(progress) {
        const percent = progress.progress_percentage || 0;
        document.getElementById('progressBar').style.width = `${percent}%`;
        document.getElementById('progressPercent').textContent = `${percent.toFixed(1)}%`;
        
        if (progress.current_chunk !== undefined && progress.total_chunks !== undefined) {
            document.getElementById('processedChunks').textContent = 
                `${progress.current_chunk}/${progress.total_chunks}`;
        }
        
        if (progress.tokens_used !== undefined) {
            document.getElementById('inputTokens').textContent = 
                Utils.formatNumber(progress.tokens_used);
        }
    },

    updateAnalysisId(id) {
        document.getElementById('analysisId').textContent = `ID: ${id}`;
    },

    setAnalyzing(isAnalyzing) {
        const analyzeBtn = document.getElementById('analyzeBtn');
        const cancelBtn = document.getElementById('cancelBtn');
        const spinner = analyzeBtn.querySelector('.spinner');
        const btnText = analyzeBtn.querySelector('span:last-child');
        
        if (isAnalyzing) {
            analyzeBtn.disabled = true;
            spinner.style.display = 'inline-block';
            btnText.textContent = '分析中...';
            cancelBtn.style.display = 'inline-flex';
            document.getElementById('progressSection').classList.add('active');
        } else {
            analyzeBtn.disabled = false;
            spinner.style.display = 'none';
            btnText.textContent = '開始分析';
            cancelBtn.style.display = 'none';
        }
    },

    enableAnalysis() {
        document.getElementById('analyzeBtn').disabled = false;
    },

    updateResults() {
        // Use marked.js for markdown parsing
        if (window.marked) {
            const html = marked.parse(window.AppState.analysisResults.content);
            document.getElementById('analysisContent').innerHTML = html;
        } else {
            // Fallback to simple parser
            const html = Utils.parseMarkdown(window.AppState.analysisResults.content);
            document.getElementById('analysisContent').innerHTML = html;
        }
        
        // Update raw content
        document.getElementById('rawContent').textContent = window.AppState.analysisResults.raw;
        
        // Syntax highlighting
        if (window.Prism) {
            Prism.highlightAllUnder(document.getElementById('analysisContent'));
        }
    },

    showResults() {
        document.getElementById('resultsSection').classList.add('active');
        Utils.scrollToElement(document.getElementById('resultsSection'), 100);
    },

    clearAll() {
        document.getElementById('fileInfo').classList.remove('active');
        document.getElementById('costSection').classList.remove('active');
        document.getElementById('progressSection').classList.remove('active');
        document.getElementById('resultsSection').classList.remove('active');
        document.getElementById('analyzeBtn').disabled = true;
        document.getElementById('analysisContent').innerHTML = '';
        document.getElementById('rawContent').textContent = '';
        document.getElementById('statusMessages').innerHTML = '';
        document.getElementById('progressBar').style.width = '0%';
    },

    handleFeedback(data) {
        const level = data.level || 'info';
        const message = data.message || '';
        
        this.showMessage(message, level);
        window.StatusMonitor.addLog(message, level);
    },

    updateStatistics(stats) {
        // This would update charts if implemented
        console.log('Statistics:', stats);
    }
};

// Export utilities
window.Utils = Utils;
window.UIController = UIController;