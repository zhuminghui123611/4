// 测试通过中继服务获取Gate.io数据
const axios = require('axios');

// 中继服务URL
const RELAY_URL = 'https://magnificent-lolly-8c4284.netlify.app';

async function testGateioRelay() {
  try {
    console.log('通过中继服务连接Gate.io...');
    
    // 构建API请求URL
    const endpoint = `${RELAY_URL}/ccxt/v1/exchanges/gateio/ticker/BTC%2FUSDT`;
    
    console.log(`请求URL: ${endpoint}`);
    const response = await axios.get(endpoint);
    
    console.log('\nGate.io BTC/USDT 行情数据:');
    console.log(JSON.stringify(response.data, null, 2));
    
    return response.data;
  } catch (error) {
    console.error('请求失败:', error.message);
    if (error.response) {
      console.error('响应状态:', error.response.status);
      console.error('响应数据:', error.response.data);
    }
    throw error;
  }
}

// 执行测试
testGateioRelay()
  .then(data => {
    console.log('\n测试完成！');
  })
  .catch(err => {
    console.error('\n测试失败。');
  }); 