import hashlib
import hmac
import base64
from typing import Optional

def generate_okx_signature(message: str, secret_key: str) -> str:
    """
    生成OKX API签名
    
    Args:
        message: 要签名的消息
        secret_key: API密钥
        
    Returns:
        str: Base64编码的HMAC签名
    """
    mac = hmac.new(
        bytes(secret_key, encoding='utf8'),
        bytes(message, encoding='utf-8'),
        digestmod=hashlib.sha256
    )
    return base64.b64encode(mac.digest()).decode('utf-8')

def sha256_hash(data: str) -> str:
    """
    计算字符串的SHA256哈希值
    
    Args:
        data: 要哈希的数据
        
    Returns:
        str: 十六进制格式的哈希值
    """
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def keccak256_hash(data: str) -> str:
    """
    计算字符串的Keccak256哈希值(以太坊常用)
    
    Args:
        data: 要哈希的数据
        
    Returns:
        str: 十六进制格式的哈希值
    """
    try:
        from eth_hash.auto import keccak
        return '0x' + keccak(data.encode('utf-8')).hex()
    except ImportError:
        raise ImportError("eth_hash库未安装，无法计算Keccak256哈希，请安装: pip install eth-hash[pycryptodome]") 