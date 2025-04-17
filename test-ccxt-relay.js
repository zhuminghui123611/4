// 测试ccxt-relay.js函数
const axios = require('axios');

// 直接引入ccxt-relay.js函数处理器
try {
  const ccxtRelay = require('./netlify/functions/ccxt-relay');
  
  console.log('==== 测试ccxt-relay.js函数 ====\n');
  
  // 测试不同的路由
  async function testRelay() {
    const testCases = [
      {
        name: '健康检查',
        event: { path: '', httpMethod: 'GET' }
      },
      {
        name: '交易所列表',
        event: { path: '/exchanges', httpMethod: 'GET' }
      },
      {
        name: 'Gate.io BTC/USDT行情',
        event: { path: '/exchange/gateio/ticker/BTC%2FUSDT', httpMethod: 'GET' }
      },
      {
        name: '404路由',
        event: { path: '/invalid/route', httpMethod: 'GET' }
      }
    ];
    
    // 依次测试每个案例
    for (const testCase of testCases) {
      console.log(`- 测试: ${testCase.name}`);
      try {
        const response = await ccxtRelay.handler(testCase.event, {});
        console.log(`  状态码: ${response.statusCode}`);
        
        // 解析响应主体并格式化显示
        if (response.body) {
          const body = JSON.parse(response.body);
          console.log(`  响应摘要: ${JSON.stringify(body).substring(0, 150)}...`);
        }
        
        console.log('  测试结果: ✓ 成功\n');
      } catch (error) {
        console.error(`  测试结果: ✗ 失败`);
        console.error(`  错误: ${error.message}\n`);
      }
    }
  }
  
  // 运行测试
  testRelay()
    .then(() => {
      console.log('==== 所有测试完成 ====');
    })
    .catch(error => {
      console.error('测试过程中发生错误:', error.message);
    });
  
} catch (error) {
  console.error('无法加载ccxt-relay.js函数:', error.message);
  
  // 检查lib/ccxt-adapter.js文件
  try {
    const fs = require('fs');
    const path = require('path');
    
    const adapterPath = path.join(__dirname, 'netlify', 'functions', 'lib', 'ccxt-adapter.js');
    if (fs.existsSync(adapterPath)) {
      const stats = fs.statSync(adapterPath);
      console.log(`\nlib/ccxt-adapter.js文件存在 (${stats.size} 字节)`);
      
      // 检查createHandler方法
      const content = fs.readFileSync(adapterPath, 'utf8');
      if (content.includes('createHandler')) {
        console.log('lib/ccxt-adapter.js文件包含createHandler方法 ✓');
      } else {
        console.log('lib/ccxt-adapter.js文件不包含createHandler方法 ✗');
      }
    } else {
      console.log('\nlib/ccxt-adapter.js文件不存在 ✗');
    }
  } catch (err) {
    console.error('检查lib/ccxt-adapter.js时出错:', err.message);
  }
} 