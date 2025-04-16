/**
 * 预测服务 - 处理所有与市场预测相关的操作
 */
const PredictionService = (() => {
    const BASE_API_URL = '/api/v1';
    
    /**
     * 获取支持的预测类型列表
     * @returns {Promise<Array>} - 支持的预测类型列表
     */
    async function getPredictionTypes() {
        try {
            const response = await fetch(`${BASE_API_URL}/prediction/types`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '获取预测类型时发生错误');
            }

            return await response.json();
        } catch (error) {
            console.error('获取预测类型失败:', error);
            throw error;
        }
    }
    
    /**
     * 获取支持的时间周期列表
     * @returns {Promise<Array>} - 支持的时间周期列表
     */
    async function getTimeHorizons() {
        try {
            const response = await fetch(`${BASE_API_URL}/prediction/horizons`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '获取时间周期时发生错误');
            }

            return await response.json();
        } catch (error) {
            console.error('获取时间周期失败:', error);
            throw error;
        }
    }
    
    /**
     * 生成市场预测
     * @param {Object} predictionRequest - 预测请求参数
     * @param {string} predictionRequest.symbol - 交易对符号
     * @param {string} predictionRequest.predictionType - 预测类型
     * @param {string} predictionRequest.timeHorizon - 时间周期
     * @param {Object} [predictionRequest.additionalFeatures] - 额外特征数据
     * @param {string} [predictionRequest.modelType] - 模型类型（默认为系统选择最优）
     * @returns {Promise<Object>} - 预测结果
     */
    async function generatePrediction(predictionRequest) {
        try {
            // 将驼峰命名转换为蛇形命名以符合后端API格式
            const requestBody = {
                symbol: predictionRequest.symbol,
                prediction_type: predictionRequest.predictionType,
                time_horizon: predictionRequest.timeHorizon
            };
            
            if (predictionRequest.additionalFeatures) {
                requestBody.additional_features = predictionRequest.additionalFeatures;
            }
            
            if (predictionRequest.modelType) {
                requestBody.model_type = predictionRequest.modelType;
            }

            const response = await fetch(`${BASE_API_URL}/prediction`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '生成预测时发生错误');
            }

            return await response.json();
        } catch (error) {
            console.error('生成预测失败:', error);
            throw error;
        }
    }
    
    /**
     * 在指定容器中显示预测结果
     * @param {HTMLElement} container - 用于显示预测结果的HTML容器元素
     * @param {Object} prediction - 预测结果对象
     */
    function displayPrediction(container, prediction) {
        if (!container || !prediction) return;
        
        container.innerHTML = '';
        
        // 创建预测结果标题
        const title = document.createElement('h3');
        title.className = 'prediction-title';
        title.textContent = `${prediction.symbol} ${prediction.prediction_type_name} 预测`;
        container.appendChild(title);
        
        // 创建预测结果内容
        const content = document.createElement('div');
        content.className = 'prediction-content';
        
        // 添加时间周期信息
        const timeHorizon = document.createElement('p');
        timeHorizon.innerHTML = `<strong>时间周期:</strong> ${prediction.time_horizon_name}`;
        content.appendChild(timeHorizon);
        
        // 添加模型信息
        const model = document.createElement('p');
        model.innerHTML = `<strong>模型:</strong> ${prediction.model_type}`;
        content.appendChild(model);
        
        // 添加预测结果
        const result = document.createElement('div');
        result.className = 'prediction-result';
        
        // 根据预测类型展示不同的结果格式
        switch(prediction.prediction_type) {
            case 'price':
                result.innerHTML = `
                    <div class="prediction-value ${prediction.direction === 'up' ? 'up' : 'down'}">
                        <span class="prediction-label">预计价格:</span>
                        <span class="prediction-number">${prediction.predicted_value.toFixed(8)}</span>
                        <span class="prediction-change">(${prediction.direction === 'up' ? '+' : ''}${prediction.change_percent.toFixed(2)}%)</span>
                    </div>
                `;
                break;
                
            case 'trend':
                result.innerHTML = `
                    <div class="prediction-trend ${prediction.predicted_value === 'bullish' ? 'up' : 'down'}">
                        <span class="prediction-label">预计趋势:</span>
                        <span class="prediction-trend-value">${prediction.predicted_value === 'bullish' ? '看涨' : '看跌'}</span>
                        <span class="prediction-confidence">(置信度: ${(prediction.confidence * 100).toFixed(2)}%)</span>
                    </div>
                `;
                break;
                
            case 'volatility':
                result.innerHTML = `
                    <div class="prediction-volatility">
                        <span class="prediction-label">预计波动率:</span>
                        <span class="prediction-number">${(prediction.predicted_value * 100).toFixed(2)}%</span>
                        <span class="prediction-range">预计范围: ${prediction.range_low.toFixed(8)} - ${prediction.range_high.toFixed(8)}</span>
                    </div>
                `;
                break;
                
            case 'signal':
                result.innerHTML = `
                    <div class="prediction-signal ${prediction.predicted_value === 'buy' ? 'buy' : prediction.predicted_value === 'sell' ? 'sell' : 'neutral'}">
                        <span class="prediction-label">交易信号:</span>
                        <span class="prediction-signal-value">${prediction.predicted_value === 'buy' ? '买入' : prediction.predicted_value === 'sell' ? '卖出' : '中性'}</span>
                        <span class="prediction-confidence">(置信度: ${(prediction.confidence * 100).toFixed(2)}%)</span>
                    </div>
                `;
                break;
                
            case 'sentiment':
                result.innerHTML = `
                    <div class="prediction-sentiment">
                        <span class="prediction-label">市场情绪:</span>
                        <span class="prediction-sentiment-value ${getSentimentClass(prediction.predicted_value)}">${formatSentiment(prediction.predicted_value)}</span>
                        <div class="sentiment-meter">
                            <div class="sentiment-bar" style="width: ${((prediction.predicted_value + 1) / 2 * 100).toFixed(0)}%"></div>
                        </div>
                    </div>
                `;
                break;
                
            case 'risk':
                result.innerHTML = `
                    <div class="prediction-risk">
                        <span class="prediction-label">风险评估:</span>
                        <span class="prediction-risk-value ${getRiskClass(prediction.predicted_value)}">${formatRisk(prediction.predicted_value)}</span>
                        <div class="risk-meter">
                            <div class="risk-bar" style="width: ${(prediction.predicted_value * 100).toFixed(0)}%"></div>
                        </div>
                    </div>
                `;
                break;
                
            default:
                result.innerHTML = `
                    <div class="prediction-default">
                        <span class="prediction-label">预测值:</span>
                        <span class="prediction-value">${prediction.predicted_value}</span>
                    </div>
                `;
        }
        
        content.appendChild(result);
        
        // 添加时间戳
        const timestamp = document.createElement('p');
        timestamp.className = 'prediction-timestamp';
        timestamp.textContent = `预测生成时间: ${new Date(prediction.timestamp).toLocaleString()}`;
        content.appendChild(timestamp);
        
        container.appendChild(content);
        
        // 如果有附加分析，显示它
        if (prediction.analysis) {
            const analysis = document.createElement('div');
            analysis.className = 'prediction-analysis';
            analysis.innerHTML = `
                <h4>附加分析</h4>
                <p>${prediction.analysis}</p>
            `;
            container.appendChild(analysis);
        }
    }
    
    /**
     * 获取情绪值对应的CSS类
     * @param {number} sentiment - 情绪值（-1到1）
     * @returns {string} - CSS类名
     */
    function getSentimentClass(sentiment) {
        if (sentiment > 0.3) return 'very-positive';
        if (sentiment > 0) return 'positive';
        if (sentiment > -0.3) return 'negative';
        return 'very-negative';
    }
    
    /**
     * 格式化情绪值为文本
     * @param {number} sentiment - 情绪值（-1到1）
     * @returns {string} - 格式化后的文本
     */
    function formatSentiment(sentiment) {
        if (sentiment > 0.3) return '非常积极';
        if (sentiment > 0) return '积极';
        if (sentiment > -0.3) return '消极';
        return '非常消极';
    }
    
    /**
     * 获取风险值对应的CSS类
     * @param {number} risk - 风险值（0到1）
     * @returns {string} - CSS类名
     */
    function getRiskClass(risk) {
        if (risk < 0.3) return 'low-risk';
        if (risk < 0.7) return 'medium-risk';
        return 'high-risk';
    }
    
    /**
     * 格式化风险值为文本
     * @param {number} risk - 风险值（0到1）
     * @returns {string} - 格式化后的文本
     */
    function formatRisk(risk) {
        if (risk < 0.3) return '低风险';
        if (risk < 0.7) return '中等风险';
        return '高风险';
    }
    
    // 公开的API
    return {
        getPredictionTypes,
        getTimeHorizons,
        generatePrediction,
        displayPrediction
    };
})();

// 如果在Node.js环境中，导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PredictionService;
} 