/**
 * 结算服务 - 处理所有与交易费用结算和分配相关的操作
 */
const SettlementService = (() => {
    const BASE_API_URL = '/api/v1';
    
    /**
     * 获取各账户的费用余额
     * @returns {Promise<Object>} - 费用余额信息
     */
    async function getFeeBalances() {
        try {
            const response = await fetch(`${BASE_API_URL}/settlements/balances`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '获取费用余额时发生错误');
            }

            return await response.json();
        } catch (error) {
            console.error('获取费用余额失败:', error);
            throw error;
        }
    }
    
    /**
     * 获取结算记录
     * @param {Object} params - 请求参数
     * @param {string} [params.startDate] - 开始日期（ISO格式）
     * @param {string} [params.endDate] - 结束日期（ISO格式）
     * @param {number} [params.limit=100] - 返回记录的最大数量
     * @returns {Promise<Array>} - 结算记录列表
     */
    async function getSettlementRecords({ startDate, endDate, limit = 100 } = {}) {
        try {
            let url = new URL(`${BASE_API_URL}/settlements/records`, window.location.origin);
            
            if (startDate) {
                url.searchParams.append('start_date', startDate);
            }
            
            if (endDate) {
                url.searchParams.append('end_date', endDate);
            }
            
            url.searchParams.append('limit', limit);
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '获取结算记录时发生错误');
            }

            return await response.json();
        } catch (error) {
            console.error('获取结算记录失败:', error);
            throw error;
        }
    }
    
    /**
     * 更新费用分配比例
     * @param {Object} distribution - 新的费用分配比例
     * @returns {Promise<Object>} - 更新后的费用分配比例
     */
    async function updateFeeDistribution(distribution) {
        try {
            const response = await fetch(`${BASE_API_URL}/settlements/distribution`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(distribution)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '更新费用分配比例时发生错误');
            }

            return await response.json();
        } catch (error) {
            console.error('更新费用分配比例失败:', error);
            throw error;
        }
    }
    
    /**
     * 从平台账户提取费用
     * @param {Object} params - 提取参数
     * @param {number} params.amount - 提取金额
     * @param {string} params.currency - 币种
     * @param {string} params.destination - 目的地地址或账户
     * @returns {Promise<Object>} - 提取操作结果
     */
    async function withdrawPlatformFee({ amount, currency, destination }) {
        try {
            const response = await fetch(`${BASE_API_URL}/settlements/withdraw/platform`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    amount,
                    currency,
                    destination
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '提取平台费用时发生错误');
            }

            return await response.json();
        } catch (error) {
            console.error('提取平台费用失败:', error);
            throw error;
        }
    }
    
    /**
     * 分配流动性提供者费用
     * @param {Array} distributionPlan - 分配计划
     * @returns {Promise<Object>} - 分配操作结果
     */
    async function distributeLiquidityProviderFees(distributionPlan) {
        try {
            const response = await fetch(`${BASE_API_URL}/settlements/distribute/liquidity`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(distributionPlan)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '分配流动性提供者费用时发生错误');
            }

            return await response.json();
        } catch (error) {
            console.error('分配流动性提供者费用失败:', error);
            throw error;
        }
    }
    
    /**
     * 生成结算报告
     * @param {Object} params - 报告参数
     * @param {string} params.period - 报告周期（daily, weekly, monthly）
     * @param {string} params.startDate - 开始日期（ISO格式）
     * @param {string} [params.endDate] - 结束日期（ISO格式）
     * @returns {Promise<Object>} - 结算报告
     */
    async function generateSettlementReport({ period, startDate, endDate }) {
        try {
            let url = new URL(`${BASE_API_URL}/settlements/report`, window.location.origin);
            
            url.searchParams.append('period', period);
            url.searchParams.append('start_date', startDate);
            
            if (endDate) {
                url.searchParams.append('end_date', endDate);
            }
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '生成结算报告时发生错误');
            }

            return await response.json();
        } catch (error) {
            console.error('生成结算报告失败:', error);
            throw error;
        }
    }
    
    /**
     * 在指定容器中显示费用余额
     * @param {HTMLElement} container - 用于显示费用余额的HTML容器元素
     * @param {Object} balanceData - 费用余额数据
     */
    function displayFeeBalances(container, balanceData) {
        if (!container || !balanceData || !balanceData.balances) return;
        
        container.innerHTML = '';
        
        // 创建标题
        const title = document.createElement('h3');
        title.className = 'balances-title';
        title.textContent = '费用余额';
        container.appendChild(title);
        
        // 创建表格
        const table = document.createElement('table');
        table.className = 'balances-table';
        
        // 表头
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        headerRow.innerHTML = `
            <th>账户</th>
            <th>余额</th>
        `;
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // 表体
        const tbody = document.createElement('tbody');
        
        for (const [account, balance] of Object.entries(balanceData.balances)) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${formatAccountName(account)}</td>
                <td>${balance.toFixed(8)}</td>
            `;
            tbody.appendChild(row);
        }
        
        table.appendChild(tbody);
        container.appendChild(table);
        
        // 添加更新时间
        const timestamp = document.createElement('p');
        timestamp.className = 'balances-timestamp';
        timestamp.textContent = `更新时间: ${new Date(balanceData.timestamp).toLocaleString()}`;
        container.appendChild(timestamp);
    }
    
    /**
     * 在指定容器中显示结算记录
     * @param {HTMLElement} container - 用于显示结算记录的HTML容器元素
     * @param {Array} records - 结算记录列表
     */
    function displaySettlementRecords(container, records) {
        if (!container || !records || !Array.isArray(records)) return;
        
        container.innerHTML = '';
        
        if (records.length === 0) {
            container.innerHTML = '<p class="no-records">暂无结算记录</p>';
            return;
        }
        
        // 创建标题
        const title = document.createElement('h3');
        title.className = 'records-title';
        title.textContent = '结算记录';
        container.appendChild(title);
        
        // 创建表格
        const table = document.createElement('table');
        table.className = 'records-table';
        
        // 表头
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        headerRow.innerHTML = `
            <th>结算ID</th>
            <th>时间</th>
            <th>订单ID</th>
            <th>费用金额</th>
            <th>币种</th>
            <th>用户ID</th>
            <th>状态</th>
        `;
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // 表体
        const tbody = document.createElement('tbody');
        
        for (const record of records) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${record.settlement_id}</td>
                <td>${new Date(record.timestamp).toLocaleString()}</td>
                <td>${record.order_id}</td>
                <td>${record.fee_amount.toFixed(8)}</td>
                <td>${record.currency}</td>
                <td>${record.user_id || '-'}</td>
                <td>${record.status}</td>
            `;
            
            // 添加点击事件显示分配详情
            row.addEventListener('click', () => {
                showDistributionDetails(record);
            });
            
            tbody.appendChild(row);
        }
        
        table.appendChild(tbody);
        container.appendChild(table);
    }
    
    /**
     * 显示分配详情
     * @param {Object} record - 结算记录
     */
    function showDistributionDetails(record) {
        // 创建详情弹窗
        const modal = document.createElement('div');
        modal.className = 'distribution-modal';
        
        const modalContent = document.createElement('div');
        modalContent.className = 'distribution-modal-content';
        
        // 添加标题
        const title = document.createElement('h4');
        title.textContent = `结算ID: ${record.settlement_id} 的分配详情`;
        modalContent.appendChild(title);
        
        // 添加分配详情表格
        const table = document.createElement('table');
        table.className = 'distribution-table';
        
        // 表头
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        headerRow.innerHTML = `
            <th>账户</th>
            <th>金额</th>
            <th>比例</th>
        `;
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // 表体
        const tbody = document.createElement('tbody');
        
        for (const [account, amount] of Object.entries(record.distribution)) {
            const ratio = amount / record.fee_amount;
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${formatAccountName(account)}</td>
                <td>${amount.toFixed(8)}</td>
                <td>${(ratio * 100).toFixed(2)}%</td>
            `;
            
            tbody.appendChild(row);
        }
        
        table.appendChild(tbody);
        modalContent.appendChild(table);
        
        // 添加关闭按钮
        const closeButton = document.createElement('button');
        closeButton.className = 'close-button';
        closeButton.textContent = '关闭';
        closeButton.addEventListener('click', () => {
            document.body.removeChild(modal);
        });
        
        modalContent.appendChild(closeButton);
        modal.appendChild(modalContent);
        
        // 添加到文档
        document.body.appendChild(modal);
    }
    
    /**
     * 格式化账户名称
     * @param {string} account - 账户名称
     * @returns {string} - 格式化后的账户名称
     */
    function formatAccountName(account) {
        switch (account) {
            case 'platform':
                return '平台账户';
            case 'liquidity_providers':
                return '流动性提供者';
            case 'risk_reserve':
                return '风险储备金';
            default:
                return account;
        }
    }
    
    // 公开的API
    return {
        getFeeBalances,
        getSettlementRecords,
        updateFeeDistribution,
        withdrawPlatformFee,
        distributeLiquidityProviderFees,
        generateSettlementReport,
        displayFeeBalances,
        displaySettlementRecords
    };
})();

// 如果在Node.js环境中，导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SettlementService;
} 