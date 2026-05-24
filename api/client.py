"""微信 iLink API 客户端"""
import hashlib
import os

import requests
import json
import base64
import random
from typing import Optional, Dict, Any
from urllib.parse import urljoin
from .types import BaseInfo
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class WeixinApiClient:
    """API客户端实现"""
    
    def __init__(self, base_url: str = "https://ilinkai.weixin.qq.com"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; OpenClaw-Weixin/1.0; Python)",
            "Accept": "application/json",
        })
        self.channel_version = "1.0.0"
    
    def _ensure_trailing_slash(self, url: str) -> str:
        """确保URL以斜杠结尾"""
        return url if url.endswith('/') else url + '/'
    
    def _random_wechat_uin(self) -> str:
        """生成随机的X-WECHAT-UIN头部值"""
        uint32 = random.getrandbits(32)
        decimal_str = str(uint32)
        return base64.b64encode(decimal_str.encode('utf-8')).decode('utf-8')
    
    def _build_headers(self, token: Optional[str] = None, body: str = "") -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "Content-Length": str(len(body.encode('utf-8'))),
            "X-WECHAT-UIN": self._random_wechat_uin(),
        }
        
        if token and token.strip():
            headers["Authorization"] = f"Bearer {token.strip()}"
        
        # SKRouteTag 暂时留空
        headers["SKRouteTag"] = ""
        
        return headers
    
    def _build_base_info(self) -> Dict[str, Any]:
        """构建基础信息"""
        return {"channel_version": self.channel_version}
    
    def api_request(self, endpoint: str, body: Dict[str, Any], 
                   token: Optional[str] = None, timeout_ms: int = 30000,
                   method: str = "POST") -> Dict[str, Any]:
        """
        通用API请求
        """
        url = urljoin(self._ensure_trailing_slash(self.base_url), endpoint)
        body_str = json.dumps({**body, "base_info": self._build_base_info()}, 
                             ensure_ascii=False)
        
        headers = self._build_headers(token, body_str)
        
        try:
            if method.upper() == "GET":
                response = self.session.get(
                    url,
                    params=body,
                    headers=headers,
                    timeout=timeout_ms/1000
                )
            else:
                response = self.session.post(
                    url,
                    data=body_str,
                    headers=headers,
                    timeout=timeout_ms/1000
                )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            raise TimeoutError(f"请求超时 ({timeout_ms}ms)")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"网络错误: {str(e)}")
    
    def get_updates(self, get_updates_buf: str = "", 
                   token: Optional[str] = None,
                   timeout_ms: int = 35000) -> Dict[str, Any]:
        """
        获取消息更新
        """
        body = {"get_updates_buf": get_updates_buf}
        
        try:
            return self.api_request(
                endpoint="ilink/bot/getupdates",
                body=body,
                token=token,
                timeout_ms=timeout_ms
            )
        except TimeoutError:
            # 长轮询超时是正常的
            return {"ret": 0, "msgs": [], "get_updates_buf": get_updates_buf}
    
    def send_message(self, msg_data: Dict[str, Any], 
                    token: Optional[str] = None,
                    timeout_ms: int = 15000) -> None:
        """
        发送消息
        """
        for i in range(3):  # 重试机制
            try:
                resp = self.api_request(
                    endpoint="ilink/bot/sendmessage",
                    body=msg_data,
                    token=token,
                    timeout_ms=timeout_ms
                )
                print(f"消息发送响应: {resp}")
                return
            except Exception as e:
                print(f"消息发送失败 (尝试 {i+1}/3): {e}")

    
    def get_qrcode(self) -> Dict[str, Any]:
        """
        获取登录二维码
        """
        response = requests.get(f"{self.base_url}/ilink/bot/get_bot_qrcode?bot_type=3", timeout=35)
        response.raise_for_status()
        return response.json()
        # return self.api_request(
        #     endpoint="ilink/bot/get_bot_qrcode",
        #     body={"bot_type": "3"},
        #     timeout_ms=60*1000,
        #     method="GET"
        # )
    
    def get_qrcode_status(self, qrcode: str) -> Dict[str, Any]:
        """
        查询二维码状态
        """
        headers = {
            "iLink-App-ClientVersion": "1",
            "SKRouteTag": "",
        }
        
        url = f"{self.base_url}/ilink/bot/get_qrcode_status"
        params = {"qrcode": qrcode}
        
        response = requests.get(url, params=params, headers=headers, timeout=35)
        response.raise_for_status()
        return response.json()
    
    def get_upload_url(self, file_path: str, to_user_id: str, media_type: int = 1) -> Optional[Dict[str, Any]]:
        """
        获取上传URL的完整实现
        
        Args:
            file_path: 文件路径
            to_user_id: 接收者用户ID
            media_type: 媒体类型 (1=图片, 2=视频, 3=文件, 4=语音)
        
        Returns:
            上传信息字典，包含upload_param和aes_key
        """
        try:
            # 1. 读取文件
            with open(file_path, "rb") as f:
                file_data = f.read()
            
            # 2. 计算文件基本信息
            file_size = len(file_data)
            file_md5 = hashlib.md5(file_data).hexdigest()
            
            # 3. 生成AES-128-ECB加密key
            aes_key = os.urandom(16)  # 16字节 = 128位
            
            # 4. 加密文件（AES-128-ECB模式）
            cipher = Cipher(
                algorithms.AES(aes_key),
                modes.ECB(),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            # AES-ECB需要将数据填充到16字节的倍数
            padding_length = 16 - (file_size % 16)
            padded_data = file_data + bytes([padding_length] * padding_length)
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
            
            encrypted_size = len(encrypted_data)
            
            # 5. 构建请求参数
            req_data = {
                "filekey": os.path.basename(file_path),
                "media_type": media_type,  # 1=图片, 2=视频, 3=文件, 4=语音
                "to_user_id": to_user_id,
                "rawsize": file_size,  # 原始文件大小
                "rawfilemd5": file_md5,  # 原始文件MD5
                "filesize": encrypted_size,  # 加密后文件大小
                "thumb_rawsize": 0,  # 缩略图原始大小（如有）
                "thumb_rawfilemd5": "",  # 缩略图MD5（如有）
                "thumb_filesize": 0,  # 缩略图加密后大小（如有）
                "no_need_thumb": True,  # 不需要缩略图
                "aeskey": base64.b64encode(aes_key).decode('utf-8'),  # base64编码的AES key
            }
            
            # 6. 调用API
            resp = self.api_client.get_upload_url_api(req_data, self.bot_token)
            
            if resp and resp.get("ret") == 0:
                upload_info = {
                    "upload_param": resp.get("upload_param"),
                    "thumb_upload_param": resp.get("thumb_upload_param"),
                    "aes_key": aes_key,
                    "original_size": file_size,
                    "encrypted_size": encrypted_size,
                    "file_md5": file_md5,
                }
                return upload_info
            else:
                print(f"❌ 获取上传URL失败: {resp}")
                return None
                
        except Exception as e:
            print(f"❌ 处理文件上传失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    def get_upload_url_api(self, req_data: Dict[str, Any], 
                        token: Optional[str] = None,
                        timeout_ms: int = 15000) -> Dict[str, Any]:
        """
        调用 getuploadurl API
        """
        try:
            # 构建完整的请求体
            full_body = {
                **req_data,
                "base_info": {"channel_version": "1.0.0"}
            }
            
            # 发送请求
            url = f"{self.base_url}/ilink/bot/getuploadurl"
            headers = {
                "Content-Type": "application/json",
                "AuthorizationType": "ilink_bot_token",
                "Authorization": f"Bearer {token}" if token else "",
                "X-WECHAT-UIN": self._random_wechat_uin(),
                "SKRouteTag": "",
            }
            
            print(f"🔍 获取上传URL请求:")
            print(f"  URL: {url}")
            print(f"  请求体: {json.dumps(full_body, indent=2, ensure_ascii=False)[:500]}...")
            
            response = self.session.post(
                url,
                json=full_body,
                headers=headers,
                timeout=timeout_ms/1000
            )
            
            response.raise_for_status()
            resp_data = response.json()
            
            print(f"✅ 获取上传URL响应: {resp_data}")
            return resp_data
            
        except Exception as e:
            print(f"❌ 获取上传URL失败: {e}")
            return {}