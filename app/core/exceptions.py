from fastapi import HTTPException, status
from typing import Any, Dict, Optional

from app.core.config import ErrorCode


class APIException(HTTPException):
    """自定义API异常基类"""
    
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        headers: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "error_code": error_code,
                "message": message
            },
            headers=headers,
        )


class BadRequestException(APIException):
    """请求参数错误异常"""
    
    def __init__(
        self, 
        message: str = "请求参数错误", 
        error_code: str = ErrorCode.BAD_REQUEST,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            message=message,
            headers=headers,
        )


class UnauthorizedException(APIException):
    """未授权异常"""
    
    def __init__(
        self, 
        message: str = "未授权访问", 
        error_code: str = ErrorCode.UNAUTHORIZED,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            message=message,
            headers=headers,
        )


class ForbiddenException(APIException):
    """权限不足异常"""
    
    def __init__(
        self, 
        message: str = "权限不足", 
        error_code: str = ErrorCode.FORBIDDEN,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=error_code,
            message=message,
            headers=headers,
        )


class NotFoundException(APIException):
    """资源不存在异常"""
    
    def __init__(
        self, 
        message: str = "请求的资源不存在", 
        error_code: str = ErrorCode.NOT_FOUND,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=error_code,
            message=message,
            headers=headers,
        )


class ValidationException(APIException):
    """数据验证异常"""
    
    def __init__(
        self, 
        message: str = "数据验证失败", 
        error_code: str = ErrorCode.VALIDATION_ERROR,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code=error_code,
            message=message,
            headers=headers,
        )


class RateLimitExceededException(APIException):
    """请求频率超限异常"""
    
    def __init__(
        self, 
        message: str = "请求频率超过限制", 
        error_code: str = ErrorCode.RATE_LIMIT_EXCEEDED,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code=error_code,
            message=message,
            headers=headers,
        )


class ServiceUnavailableException(APIException):
    """服务不可用异常"""
    
    def __init__(
        self, 
        message: str = "服务暂时不可用", 
        error_code: str = ErrorCode.SERVICE_UNAVAILABLE,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code=error_code,
            message=message,
            headers=headers,
        )


class ExternalAPIException(Exception):
    """外部API调用异常"""
    
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)
    
    def __str__(self) -> str:
        return f"[{self.status_code}] {self.message}"


class InternalServerException(APIException):
    """服务器内部错误异常"""
    
    def __init__(
        self, 
        message: str = "服务器内部错误", 
        error_code: str = ErrorCode.INTERNAL_ERROR,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            message=message,
            headers=headers,
        ) 