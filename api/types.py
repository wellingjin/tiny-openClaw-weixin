"""API 数据类型定义"""
from dataclasses import dataclass, asdict
from enum import IntEnum
from typing import Optional, Dict, Any, List
import json

# 枚举定义
class MessageItemType(IntEnum):
    NONE = 0
    TEXT = 1
    IMAGE = 2  # ✅ 正确：IMAGE = 2
    VOICE = 3
    FILE = 4
    VIDEO = 5

class MessageType(IntEnum):
    NONE = 0
    USER = 1
    BOT = 2  # ✅ 正确：BOT = 2

class MessageState(IntEnum):
    NEW = 0
    GENERATING = 1
    FINISH = 2  # ✅ 正确：FINISH = 2

# 数据结构
@dataclass
class WeixinApiOptions:
    """API配置选项"""
    baseUrl: str
    token: Optional[str] = None
    timeoutMs: int = 30000
    longPollTimeoutMs: int = 35000
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class BaseInfo:
    """请求基础信息"""
    channel_version: str = "1.0.0"

@dataclass
class UploadedFileInfo:
    """已上传文件信息"""
    filekey: str
    fileSize: int
    fileSizeCiphertext: int
    aeskey: bytes
    downloadEncryptedQueryParam: str

@dataclass
class AccountData:
    """账号数据"""
    account_id: str
    bot_token: str
    ilink_bot_id: str
    ilink_user_id: str
    base_url: str
    saved_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AccountData':
        return cls(**data)