/**
 * ANR/Tombstone AI 分析系統 - 圖表管理模組
 * 
 * 負責所有資料視覺化功能，包括：
 * - Token 使用統計
 * - 成本分析
 * - 效能指標
 * - 歷史趨勢
 */

const ChartManager = {
    // 圖表實例存儲
    charts: {},
    
    // 預設配置
    defaultOptions: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'bottom',
                labels: {
                    font: {
                        family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                        size: 12
                    },
                    padding: 20
                }
            },
            tooltip: {
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                padding: 12,
                cornerRadius: 8,
                titleFont: {
                    size: 14,
                    weight: 'bold'
                },
                bodyFont: {
                    size: 13
                },
                callbacks: {
                    label: function(context) {
                        let label = context.dataset.label || '';
                        if (label) {
                            label += ': ';
                        }
                        if (context.parsed.y !== null) {
                            label += Utils.formatNumber(context.parsed.y);
                        }
                        return label;
                    }
                }
            }
        }
    },

    // 顏色方案
    colorSchemes: {
        primary: [
            '#2563eb', // Primary Blue
            '#10b981', // Success Green
            '#f59e0b', // Warning Yellow
            '#ef4444', // Danger Red
            '#8b5cf6', // Purple
            '#06b6d4', // Cyan
            '#ec4899', // Pink
            '#14b8a6'  // Teal
        ],
        gradient: {
            blue: ['rgba(37, 99, 235, 0.8)', 'rgba(37, 99, 235, 0.2)'],
            green: ['rgba(16, 185, 129, 0.8)', 'rgba(16, 185, 129, 0.2)'],
            yellow: ['rgba(245, 158, 11, 0.8)', 'rgba(245, 158, 11, 0.2)'],
            red: ['rgba(239, 68, 68, 0.8)', 'rgba(239, 68, 68, 0.2)']
        }
    },

    /**
     * 初始化圖表管理器
     */
    init() {
        // 設定全局預設值
        if (window.Chart) {
            Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
            Chart.defaults.color = '#6b7280';
        }
        
        // 監聽視窗大小變化
        window.addEventListener('resize', this.debounce(() => {
            this.resizeAllCharts();
        }, 250));
    },

    /**
     * 創建 Token 使用統計圖表
     */
    createTokenChart(canvasId, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        // 銷毀舊圖表
        this.destroyChart(canvasId);

        const config = {
            type: 'doughnut',
            data: {
                labels: ['輸入 Tokens', '輸出 Tokens'],
                datasets: [{
                    data: [data.inputTokens || 0, data.outputTokens || 0],
                    backgroundColor: [
                        this.colorSchemes.primary[0],
                        this.colorSchemes.primary[1]
                    ],
                    borderWidth: 0,
                    hoverOffset: 10
                }]
            },
            options: {
                ...this.defaultOptions,
                plugins: {
                    ...this.defaultOptions.plugins,
                    title: {
                        display: true,
                        text: 'Token 使用分佈',
                        font: {
                            size: 16,
                            weight: 'bold'
                        },
                        padding: {
                            bottom: 20
                        }
                    }
                }
            }
        };

        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    },

    /**
     * 創建成本分析圖表
     */
    createCostChart(canvasId, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        this.destroyChart(canvasId);

        const config = {
            type: 'bar',
            data: {
                labels: data.labels || ['輸入成本', '輸出成本', '總成本'],
                datasets: [{
                    label: '成本 (USD)',
                    data: data.values || [0, 0, 0],
                    backgroundColor: [
                        this.colorSchemes.primary[0],
                        this.colorSchemes.primary[1],
                        this.colorSchemes.primary[2]
                    ],
                    borderWidth: 0,
                    borderRadius: 8,
                    barThickness: 40
                }]
            },
            options: {
                ...this.defaultOptions,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        },
                        grid: {
                            drawBorder: false,
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                },
                plugins: {
                    ...this.defaultOptions.plugins,
                    title: {
                        display: true,
                        text: '成本分析',
                        font: {
                            size: 16,
                            weight: 'bold'
                        },
                        padding: {
                            bottom: 20
                        }
                    },
                    legend: {
                        display: false
                    }
                }
            }
        };

        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    },

    /**
     * 創建時間序列圖表（歷史趨勢）
     */
    createTimeSeriesChart(canvasId, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        this.destroyChart(canvasId);

        const config = {
            type: 'line',
            data: {
                labels: data.labels || [],
                datasets: data.datasets || []
            },
            options: {
                ...this.defaultOptions,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'day',
                            displayFormats: {
                                day: 'MM/DD'
                            }
                        },
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            drawBorder: false,
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    }
                },
                plugins: {
                    ...this.defaultOptions.plugins,
                    title: {
                        display: true,
                        text: data.title || '歷史趨勢',
                        font: {
                            size: 16,
                            weight: 'bold'
                        },
                        padding: {
                            bottom: 20
                        }
                    }
                }
            }
        };

        // 為每個數據集添加樣式
        config.data.datasets = config.data.datasets.map((dataset, index) => ({
            ...dataset,
            borderColor: this.colorSchemes.primary[index % this.colorSchemes.primary.length],
            backgroundColor: 'transparent',
            borderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6,
            tension: 0.1
        }));

        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    },

    /**
     * 創建雷達圖（模型比較）
     */
    createRadarChart(canvasId, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        this.destroyChart(canvasId);

        const config = {
            type: 'radar',
            data: {
                labels: data.labels || ['速度', '準確度', '成本效益', '詳細程度', '穩定性'],
                datasets: data.datasets || []
            },
            options: {
                ...this.defaultOptions,
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 5,
                        ticks: {
                            stepSize: 1
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    }
                },
                plugins: {
                    ...this.defaultOptions.plugins,
                    title: {
                        display: true,
                        text: '模型能力比較',
                        font: {
                            size: 16,
                            weight: 'bold'
                        },
                        padding: {
                            bottom: 20
                        }
                    }
                }
            }
        };

        // 為每個數據集添加樣式
        config.data.datasets = config.data.datasets.map((dataset, index) => ({
            ...dataset,
            borderColor: this.colorSchemes.primary[index % this.colorSchemes.primary.length],
            backgroundColor: this.colorSchemes.primary[index % this.colorSchemes.primary.length] + '33',
            borderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6
        }));

        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    },

    /**
     * 創建混合圖表（成本 vs 時間）
     */
    createMixedChart(canvasId, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        this.destroyChart(canvasId);

        const config = {
            type: 'bar',
            data: {
                labels: data.labels || [],
                datasets: [
                    {
                        label: '成本 (USD)',
                        data: data.costs || [],
                        backgroundColor: this.colorSchemes.primary[0],
                        borderWidth: 0,
                        borderRadius: 8,
                        yAxisID: 'y',
                        order: 2
                    },
                    {
                        label: '處理時間 (分鐘)',
                        data: data.times || [],
                        type: 'line',
                        borderColor: this.colorSchemes.primary[1],
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        yAxisID: 'y1',
                        order: 1
                    }
                ]
            },
            options: {
                ...this.defaultOptions,
                scales: {
                    x: {
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        },
                        grid: {
                            drawBorder: false,
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return value + ' 分鐘';
                            }
                        },
                        grid: {
                            drawOnChartArea: false
                        }
                    }
                },
                plugins: {
                    ...this.defaultOptions.plugins,
                    title: {
                        display: true,
                        text: '成本與時間分析',
                        font: {
                            size: 16,
                            weight: 'bold'
                        },
                        padding: {
                            bottom: 20
                        }
                    }
                }
            }
        };

        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    },

    /**
     * 創建統計摘要圖表
     */
    createSummaryChart(canvasId, stats) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        this.destroyChart(canvasId);

        // 計算統計數據
        const totalTokens = stats.inputTokens + stats.outputTokens;
        const avgTokensPerSecond = stats.duration > 0 ? 
            Math.round(totalTokens / (stats.duration / 1000)) : 0;

        const config = {
            type: 'bar',
            data: {
                labels: ['總 Tokens', '每秒 Tokens', '持續時間(秒)'],
                datasets: [{
                    data: [
                        totalTokens,
                        avgTokensPerSecond,
                        Math.round(stats.duration / 1000)
                    ],
                    backgroundColor: [
                        this.colorSchemes.primary[0],
                        this.colorSchemes.primary[1],
                        this.colorSchemes.primary[2]
                    ],
                    borderWidth: 0,
                    borderRadius: 8
                }]
            },
            options: {
                ...this.defaultOptions,
                indexAxis: 'y',
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: {
                            drawBorder: false,
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    y: {
                        grid: {
                            display: false
                        }
                    }
                },
                plugins: {
                    ...this.defaultOptions.plugins,
                    legend: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: '分析統計摘要',
                        font: {
                            size: 16,
                            weight: 'bold'
                        },
                        padding: {
                            bottom: 20
                        }
                    }
                }
            }
        };

        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    },

    /**
     * 更新圖表數據
     */
    updateChart(canvasId, newData) {
        const chart = this.charts[canvasId];
        if (!chart) return;

        // 更新數據
        if (newData.labels) {
            chart.data.labels = newData.labels;
        }
        
        if (newData.datasets) {
            chart.data.datasets = newData.datasets;
        } else if (newData.data) {
            chart.data.datasets[0].data = newData.data;
        }

        // 更新圖表
        chart.update('active');
    },

    /**
     * 銷毀圖表
     */
    destroyChart(canvasId) {
        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
            delete this.charts[canvasId];
        }
    },

    /**
     * 銷毀所有圖表
     */
    destroyAllCharts() {
        Object.keys(this.charts).forEach(canvasId => {
            this.destroyChart(canvasId);
        });
    },

    /**
     * 調整所有圖表大小
     */
    resizeAllCharts() {
        Object.values(this.charts).forEach(chart => {
            chart.resize();
        });
    },

    /**
     * 導出圖表為圖片
     */
    exportChart(canvasId, filename = 'chart.png') {
        const chart = this.charts[canvasId];
        if (!chart) return;

        const url = chart.toBase64Image();
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.click();
    },

    /**
     * 創建迷你圖表（Sparkline）
     */
    createSparkline(canvasId, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        this.destroyChart(canvasId);

        const config = {
            type: 'line',
            data: {
                labels: data.labels || Array(data.values.length).fill(''),
                datasets: [{
                    data: data.values,
                    borderColor: data.color || this.colorSchemes.primary[0],
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.1,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        enabled: false
                    }
                },
                scales: {
                    x: {
                        display: false
                    },
                    y: {
                        display: false
                    }
                },
                elements: {
                    line: {
                        borderJoinStyle: 'round'
                    }
                }
            }
        };

        this.charts[canvasId] = new Chart(ctx, config);
        return this.charts[canvasId];
    },

    /**
     * 創建儀表板圖表集合
     */
    createDashboard(data) {
        // Token 使用統計
        if (data.tokenStats) {
            this.createTokenChart('tokenChart', data.tokenStats);
        }

        // 成本分析
        if (data.costAnalysis) {
            this.createCostChart('costChart', data.costAnalysis);
        }

        // 歷史趨勢
        if (data.history) {
            this.createTimeSeriesChart('historyChart', {
                title: '7天分析趨勢',
                labels: data.history.dates,
                datasets: [
                    {
                        label: '分析次數',
                        data: data.history.counts
                    },
                    {
                        label: '平均成本',
                        data: data.history.avgCosts
                    }
                ]
            });
        }

        // 模型比較
        if (data.modelComparison) {
            this.createRadarChart('modelChart', data.modelComparison);
        }
    },

    /**
     * 工具函數：防抖
     */
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

    /**
     * 生成漸變色
     */
    createGradient(ctx, colorStart, colorEnd) {
        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, colorStart);
        gradient.addColorStop(1, colorEnd);
        return gradient;
    },

    /**
     * 格式化數據標籤
     */
    formatDataLabel(value, type = 'number') {
        switch (type) {
            case 'currency':
                return '$' + value.toFixed(2);
            case 'percentage':
                return value.toFixed(1) + '%';
            case 'time':
                return value + ' 分鐘';
            default:
                return Utils.formatNumber(value);
        }
    }
};

// 初始化圖表管理器
document.addEventListener('DOMContentLoaded', () => {
    ChartManager.init();
});

// 導出給全局使用
window.ChartManager = ChartManager;