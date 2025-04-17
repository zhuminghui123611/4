// 测试Netlify函数本地连通性
const axios = require('axios');
const path = require('path');
const fs = require('fs');

// Netlify函数路径
const FUNCTIONS_DIR = path.join(__dirname, 'netlify', 'functions');

// 检查函数文件是否存在
async function checkFunctionFiles() {
  console.log('检查Netlify函数文件...');
  const functionFiles = [
    'ccxt-api.js',
    'ccxt-adapter.js',
    'ccxt-relay.js',
    'ccxt-simple.js',
    'api.js'
  ];
  
  for (const file of functionFiles) {
    const filePath = path.join(FUNCTIONS_DIR, file);
    try {
      const stats = fs.statSync(filePath);
      console.log(`✓ ${file} (${stats.size} 字节)`);
      
      // 显示文件的前10行
      const content = fs.readFileSync(filePath, 'utf8');
      const lines = content.split('\n').slice(0, 10).join('\n');
      console.log(`  预览: \n${lines}\n  ...\n`);
    } catch (error) {
      console.error(`✗ ${file} - 找不到文件或无法读取`);
    }
  }
}

// 检查CCXT库是否安装
async function checkCcxtInstallation() {
  console.log('\n检查CCXT库安装...');
  try {
    const ccxt = require('ccxt');
    console.log(`✓ CCXT版本: ${ccxt.version}`);
    console.log(`✓ 支持的交易所: ${ccxt.exchanges.length} 个`);
  } catch (error) {
    console.error('✗ CCXT库未安装或无法加载:', error.message);
  }
}

// 测试直接调用函数
async function testDirectFunctionCalls() {
  console.log('\n测试直接调用函数...');
  
  try {
    // 测试ccxt-api.js
    const ccxtApi = require('./netlify/functions/ccxt-api');
    console.log('✓ 成功加载 ccxt-api.js');
    
    // 模拟Netlify函数调用环境
    const mockEvent = {
      path: '/health',
      httpMethod: 'GET'
    };
    
    const response = await ccxtApi.handler(mockEvent, {});
    console.log(`✓ ccxt-api健康检查结果: 状态码 ${response.statusCode}`);
    console.log(`  响应体: ${response.body}`);
  } catch (error) {
    console.error('✗ 直接调用函数失败:', error.message);
  }
}

// 执行所有测试
async function runAllTests() {
  console.log('======= Netlify函数连通性测试 =======\n');
  
  await checkFunctionFiles();
  await checkCcxtInstallation();
  await testDirectFunctionCalls();
  
  console.log('\n======= 测试完成 =======');
}

// 运行测试
runAllTests(); 