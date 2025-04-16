/**
 * 费用计算和管理模块
 * 提供与后端费用服务交互的前端功能
 */

// 基础API URL
const API_BASE_URL = '/api/v1';

/**
 * 计算交易费用
 * @param {string} symbol - 交易对符号，如 "BTC/USDT"
 * @param {number} amount - 交易数量
 * @param {number} price - 交易价格
 * @param {string} platformType - 平台类型 (CEX, DEX, P2P)
 * @param {number|null} customSlippageRate - 自定义滑点率（可选）
 * @param {number|null} customRoutingFee - 自定义路由费（可选）
 * @param {string} userTier - 用户等级 (basic, silver, gold, platinum)
 * @returns {Promise<Object>} - 费用计算结果
 */
async function calculateFees(symbol, amount, price, platformType = 'CEX', customSlippageRate = null, customRoutingFee = null, userTier = 'basic') {
    try {
        // 构建URL和查询参数
        let url = new URL(`${API_BASE_URL}/fees/calculate`, window.location.origin);
        url.searchParams.append('symbol', symbol);
        url.searchParams.append('amount', amount);
        url.searchParams.append('price', price);
        url.searchParams.append('platform_type', platformType);
        url.searchParams.append('user_tier', userTier);
        
        if (customSlippageRate !== null) {
            url.searchParams.append('custom_slippage_rate', customSlippageRate);
        }
        
        if (customRoutingFee !== null) {
            url.searchParams.append('custom_routing_fee', customRoutingFee);
        }
        
        // 发送请求
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        });
        
        // 处理响应
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '计算费用失败');
        }
        
        const result = await response.json();
        return result.data;
    } catch (error) {
        console.error('计算费用时出错:', error);
        throw error;
    }
}

/**
 * 将费用应用到订单
 * @param {Object} order - 订单对象
 * @param {Object} feeDetails - 费用详情对象
 * @returns {Promise<Object>} - 更新后的订单
 */
async function applyFeesToOrder(order, feeDetails) {
    try {
        const response = await fetch(`${API_BASE_URL}/fees/apply-to-order`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                order: order,
                fee_details: feeDetails
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '应用费用到订单失败');
        }
        
        const result = await response.json();
        return result.data;
    } catch (error) {
        console.error('应用费用到订单时出错:', error);
        throw error;
    }
}

/**
 * 获取费用配置
 * @returns {Promise<Object>} - 当前费用配置
 */
async function getFeeConfiguration() {
    try {
        const response = await fetch(`${API_BASE_URL}/fees/configuration`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '获取费用配置失败');
        }
        
        const result = await response.json();
        return result.data;
    } catch (error) {
        console.error('获取费用配置时出错:', error);
        throw error;
    }
}

/**
 * 更新费用配置
 * @param {Object} config - 新的费用配置
 * @returns {Promise<Object>} - 更新后的费用配置
 */
async function updateFeeConfiguration(config) {
    try {
        const response = await fetch(`${API_BASE_URL}/fees/configuration`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '更新费用配置失败');
        }
        
        const result = await response.json();
        return result.data;
    } catch (error) {
        console.error('更新费用配置时出错:', error);
        throw error;
    }
}

/**
 * 显示费用计算结果
 * @param {HTMLElement} container - 显示结果的容器元素
 * @param {Object} feeDetails - 费用详情对象
 */
function displayFeeDetails(container, feeDetails) {
    // 清空容器
    container.innerHTML = '';
    
    // 创建费用详情表格
    const table = document.createElement('table');
    table.className = 'fee-details-table';
    
    // 添加表头
    const thead = document.createElement('thead');
    thead.innerHTML = `
        <tr>
            <th>费用类型</th>
            <th>金额</th>
        </tr>
    `;
    table.appendChild(thead);
    
    // 添加表体
    const tbody = document.createElement('tbody');
    
    // 添加滑点费行
    const slippageRow = document.createElement('tr');
    slippageRow.innerHTML = `
        <td>滑点费</td>
        <td>${feeDetails.slippage_fee.toFixed(8)} USD</td>
    `;
    tbody.appendChild(slippageRow);
    
    // 添加路由费行
    const routingRow = document.createElement('tr');
    routingRow.innerHTML = `
        <td>路由费</td>
        <td>${feeDetails.routing_fee.toFixed(8)} USD</td>
    `;
    tbody.appendChild(routingRow);
    
    // 添加总费用行
    const totalRow = document.createElement('tr');
    totalRow.innerHTML = `
        <td><strong>总费用</strong></td>
        <td><strong>${feeDetails.total_fee.toFixed(8)} USD</strong></td>
    `;
    tbody.appendChild(totalRow);
    
    // 添加基础代币费用行
    const baseTokenRow = document.createElement('tr');
    baseTokenRow.innerHTML = `
        <td>基础代币费用</td>
        <td>${feeDetails.base_token_fee.toFixed(8)} ${feeDetails.base_token}</td>
    `;
    tbody.appendChild(baseTokenRow);
    
    // 添加有效费率行
    const effectiveRateRow = document.createElement('tr');
    effectiveRateRow.innerHTML = `
        <td>有效费率</td>
        <td>${(feeDetails.effective_fee_rate * 100).toFixed(4)}%</td>
    `;
    tbody.appendChild(effectiveRateRow);
    
    table.appendChild(tbody);
    container.appendChild(table);
    
    // 添加费用详情描述
    const description = document.createElement('div');
    description.className = 'fee-description';
    description.innerHTML = `
        <p>费用明细:</p>
        <ul>
            <li>交易对: ${feeDetails.symbol}</li>
            <li>交易金额: ${feeDetails.amount} ${feeDetails.base_token}</li>
            <li>价格: ${feeDetails.price} USD</li>
            <li>USD总价值: ${feeDetails.usd_value.toFixed(2)} USD</li>
            <li>平台类型: ${feeDetails.platform_type}</li>
            <li>用户等级: ${feeDetails.user_tier}</li>
        </ul>
    `;
    container.appendChild(description);
}

// 导出函数供其他模块使用
window.FeeService = {
    calculateFees,
    applyFeesToOrder,
    getFeeConfiguration,
    updateFeeConfiguration,
    displayFeeDetails
}; 