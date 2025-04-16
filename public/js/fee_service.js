/**
 * 费用计算服务 - 处理所有与交易费用相关的计算和操作
 */
const FeeService = (() => {
    const BASE_API_URL = '/api/v1';
    
    /**
     * 计算交易费用
     * @param {Object} params - 计算费用所需参数
     * @param {string} params.symbol - 交易对符号
     * @param {number} params.amount - 交易数量
     * @param {number} params.price - 交易价格
     * @param {string} params.platformType - 平台类型
     * @param {number} [params.customSlippageRate] - 自定义滑点率
     * @param {number} [params.customRoutingFee] - 自定义路由费
     * @param {string} [params.userTier] - 用户等级，影响费率
     * @returns {Promise<Object>} - 计算出的费用详情
     */
    async function calculateFees({ symbol, amount, price, platformType, customSlippageRate, customRoutingFee, userTier }) {
        try {
            const requestBody = {
                symbol,
                amount,
                price,
                platform_type: platformType
            };

            // 添加可选参数
            if (customSlippageRate !== undefined) {
                requestBody.custom_slippage_rate = customSlippageRate;
            }

            if (customRoutingFee !== undefined) {
                requestBody.custom_routing_fee = customRoutingFee;
            }

            if (userTier) {
                requestBody.user_tier = userTier;
            }

            const response = await fetch(`${BASE_API_URL}/trading/calculate-fees`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '计算费用时发生错误');
            }

            return await response.json();
        } catch (error) {
            console.error('计算费用失败:', error);
            throw error;
        }
    }

    /**
     * 将费用应用到订单
     * @param {Object} orderRequest - 创建订单请求对象
     * @returns {Promise<Object>} - 创建的订单结果
     */
    async function applyFeesToOrder(orderRequest) {
        try {
            const response = await fetch(`${BASE_API_URL}/trading/order`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(orderRequest)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '应用费用到订单时发生错误');
            }

            return await response.json();
        } catch (error) {
            console.error('应用费用到订单失败:', error);
            throw error;
        }
    }

    /**
     * 获取当前费用配置
     * @returns {Promise<Object>} - 当前费用配置
     */
    async function getFeeConfiguration() {
        try {
            const response = await fetch(`${BASE_API_URL}/config/fees`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '获取费用配置时发生错误');
            }

            return await response.json();
        } catch (error) {
            console.error('获取费用配置失败:', error);
            throw error;
        }
    }

    /**
     * 更新费用配置（需要管理员权限）
     * @param {Object} config - 新的费用配置
     * @returns {Promise<Object>} - 更新后的费用配置
     */
    async function updateFeeConfiguration(config) {
        try {
            const response = await fetch(`${BASE_API_URL}/config/fees`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '更新费用配置时发生错误');
            }

            return await response.json();
        } catch (error) {
            console.error('更新费用配置失败:', error);
            throw error;
        }
    }

    /**
     * 在指定容器中显示费用详情
     * @param {HTMLElement} container - 用于显示费用详情的HTML容器元素
     * @param {Object} feeDetails - 费用详情对象
     */
    function displayFeeDetails(container, feeDetails) {
        if (!container || !feeDetails) return;
        
        container.innerHTML = '';
        
        // 创建表格显示费用详情
        const table = document.createElement('table');
        table.className = 'fee-details-table';
        
        // 表头
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        headerRow.innerHTML = `
            <th>费用类型</th>
            <th>金额</th>
            <th>百分比</th>
        `;
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // 表体
        const tbody = document.createElement('tbody');
        
        // 滑点费用行
        const slippageRow = document.createElement('tr');
        slippageRow.innerHTML = `
            <td>滑点费用</td>
            <td>${feeDetails.slippage_fee.toFixed(8)}</td>
            <td>${(feeDetails.slippage_rate * 100).toFixed(4)}%</td>
        `;
        tbody.appendChild(slippageRow);
        
        // 路由费用行
        const routingRow = document.createElement('tr');
        routingRow.innerHTML = `
            <td>路由费用</td>
            <td>${feeDetails.routing_fee.toFixed(8)}</td>
            <td>${feeDetails.routing_fee > 0 ? '固定费用' : '0'}</td>
        `;
        tbody.appendChild(routingRow);
        
        // 总费用行
        const totalRow = document.createElement('tr');
        totalRow.className = 'total-fee-row';
        totalRow.innerHTML = `
            <td><strong>总费用</strong></td>
            <td><strong>${feeDetails.total_fee.toFixed(8)}</strong></td>
            <td>-</td>
        `;
        tbody.appendChild(totalRow);
        
        table.appendChild(tbody);
        container.appendChild(table);
        
        // 添加交易摘要
        const summary = document.createElement('div');
        summary.className = 'fee-summary';
        summary.innerHTML = `
            <h4>交易摘要</h4>
            <p>交易对: ${feeDetails.symbol}</p>
            <p>交易数量: ${feeDetails.amount}</p>
            <p>交易价格: ${feeDetails.price}</p>
            <p>交易总值: ${(feeDetails.amount * feeDetails.price).toFixed(8)}</p>
            <p>费用后总值: ${((feeDetails.amount * feeDetails.price) - feeDetails.total_fee).toFixed(8)}</p>
        `;
        container.appendChild(summary);
    }

    // 公开的API
    return {
        calculateFees,
        applyFeesToOrder,
        getFeeConfiguration,
        updateFeeConfiguration,
        displayFeeDetails
    };
})();

// 如果在Node.js环境中，导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = FeeService;
} 