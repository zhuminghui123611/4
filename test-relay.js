// 测试AllOrigins中继服务连通性
const axios = require('axios');

// 中继服务URL
const RELAY_URL = 'https://api.allorigins.win/raw?url=';
const TEST_API = 'https://api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT';

async function testRelay() {
  console.log('开始测试中继服务连通性...');
  
  try {
    // 直接请求测试
    console.log('1. 直接请求测试:');
    const directResponse = await axios.get(TEST_API);
    console.log('直接请求成功!');
    console.log('数据示例:', JSON.stringify(directResponse.data).substring(0, 150) + '...');
    
    // 通过中继服务请求测试
    console.log('\n2. 通过中继服务请求测试:');
    const relayUrl = `${RELAY_URL}${encodeURIComponent(TEST_API)}`;
    console.log('中继URL:', relayUrl);
    
    const relayResponse = await axios.get(relayUrl);
    console.log('中继请求成功!');
    console.log('数据示例:', JSON.stringify(relayResponse.data).substring(0, 150) + '...');
    
    console.log('\n总结: 中继服务可用 ✓');
  } catch (error) {
    console.error('\n测试失败!');
    
    if (error.response) {
      console.error('状态码:', error.response.status);
      console.error('响应数据:', error.response.data);
    } else if (error.request) {
      console.error('没有收到响应');
    } else {
      console.error('错误信息:', error.message);
    }
    
    console.error('\n总结: 中继服务不可用 ✗');
  }
}

// 执行测试
testRelay(); 