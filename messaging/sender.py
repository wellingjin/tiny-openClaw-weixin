"""消息发送模块"""
import base64
import hashlib
import os
import uuid
import re
from typing import Optional, Dict, Any
from api.types import MessageItemType, MessageType, MessageState, WeixinApiOptions
from api.client import WeixinApiClient
from media.cdnManager import CDNManager
from messaging.msgHistoryManager import msgHistoryManager

class MessageSender:
    """消息发送器"""
    
    def __init__(self, api_client: WeixinApiClient):
        self.api_client = api_client
        self.cndManager = CDNManager()
    
    def markdown_to_plain_text(self, text: str) -> str:
        """Markdown转纯文本"""
        result = text
        
        # 移除代码块标记
        result = re.sub(r'```[^\n]*\n?([\s\S]*?)```', 
                       lambda m: m.group(1).strip(), result)
        
        # 移除图片标记
        result = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', result)
        
        # 链接：保留显示文本
        result = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', result)
        
        # 表格处理
        result = re.sub(r'^\|[\s:|-]+\|$', '', result, flags=re.MULTILINE)
        
        def process_table_row(match):
            cells = [cell.strip() for cell in match.group(1).split('|')]
            return '  '.join(cells)
        
        result = re.sub(r'^\|(.+)\|$', process_table_row, result, flags=re.MULTILINE)
        
        return result.strip()
    
    def _generate_client_id(self) -> str:
        """生成客户端ID"""
        return f"openclaw-weixin-{uuid.uuid4().hex[:16]}"
    
    def build_text_message(self, to: str, text: str, context_token: str) -> tuple[Dict[str, Any], str]:
        """构建文本消息请求"""
        client_id = self._generate_client_id()
        
        item_list = []
        if text and text.strip():
            plain_text = self.markdown_to_plain_text(text)
            item_list.append({
                "type": MessageItemType.TEXT.value,
                "text_item": {"text": plain_text}
            })
        
        msg = {
            "from_user_id": "",
            "to_user_id": to,
            "client_id": client_id,
            "message_type": MessageType.BOT.value,
            "message_state": MessageState.FINISH.value,
            "context_token": context_token,
            "base_info": {"channel_version": "1.0.0"}
        }
        
        if item_list:
            msg["item_list"] = item_list
        
        return {"msg": msg}, client_id
    
    def send_text(self, to: str, text: str, context_token: str, 
                 bot_token: str) -> Optional[str]:
        """
        发送文本消息
        返回: 消息ID
        """
        if not context_token:
            raise ValueError("context_token 是必需的")
        
        if not bot_token:
            raise ValueError("未提供 bot_token")
        
        msg_data, client_id = self.build_text_message(to, text, context_token)
        
        try:
            msgHistoryManager.save_message(msg_data)
            self.api_client.send_message(msg_data, bot_token)
            return client_id
        except Exception as e:
            print(f"发送消息失败: {e}")
            return None
    
    def send_auto_reply(self, to_user_id: str, text: str, context_token: str, 
                       bot_token: str) -> Optional[str]:
        """
        发送自动回复
        """
        import time
        
        if "你好" in text or "hello" in text.lower():
            reply_text = "你好！我是 Python 实现的微信机器人。"
        elif "时间" in text:
            reply_text = f"当前时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        elif "帮助" in text or "help" in text.lower():
            reply_text = "支持功能:\n1. 文本对话\n2. 查询时间\n3. 简单问答\n4. 文件传输"
        else:
            reply_text = f"已收到你的消息: {text[:50]}..."
        
        return self.send_text(to_user_id, reply_text, context_token, bot_token)
    
    def upload_media(self, file_path: str, to_user_id: str, media_type: int, **kwargs) -> dict:
        """
        通用的媒体文件上传方法
        :param file_path: 本地文件路径
        :param to_user_id: 接收方用户ID
        :param media_type: 媒体类型 (1:图片, 2:视频, 4:文件)
        :param kwargs: 额外参数，如视频时长duration、文件名fileName等
        """
        # 1. 准备文件基础信息
        raw_size = os.path.getsize(file_path)
        with open(file_path, "rb") as f:
            plaintext = f.read()
        raw_md5 = hashlib.md5(plaintext).hexdigest()
        filekey = kwargs.get("fileName", os.path.basename(file_path))

        # 2. 获取上传信息
        upload_info = self._get_upload_info(to_user_id, filekey, raw_size, raw_md5, media_type)
        
        # 3. 加密文件
        ciphertext = self._encrypt_aes_ecb(plaintext, upload_info["aes_key"])
        # 注意：加密后的文件大小可能变化
        encrypted_size = len(ciphertext)
        
        # 4. 上传到CDN
        encrypted_query_param = self._upload_to_cdn(upload_info["upload_param"], ciphertext)
        
        # 5. 准备返回给发送接口的媒体信息
        media_info = {
            "filekey": filekey,
            "encrypt_query_param": encrypted_query_param,
            "aes_key": base64.b64encode(upload_info["aes_key"]).decode('ascii'),
            "filesize": encrypted_size # 使用加密后的大小
        }

        # 针对视频，需要额外处理缩略图
        if media_type == 2: # 视频
            # 需要先提取视频第一帧作为缩略图并上传
            # 然后调用_get_upload_info获取缩略图上传信息
            # 这里简化处理，理想情况需要实现类似逻辑[reference:4]
            # 视频消息还需携带时长(秒)
            media_info["duration"] = kwargs.get("duration", 0)
            # 添加缩略图信息
            # media_info["thumb_info"] = {...}

        # 针对普通文件，需要指定文件名
        if media_type == 4: # 文件
            media_info["file_name"] = kwargs.get("fileName", filekey)

        return media_info
    
    def upload_image_to_cdn(self, file_path: str, to_user_id: str, bot_token: str) -> Dict[str, Any]:
        """
        上传图片到微信CDN
        """
        # 1. 读取文件
        with open(file_path, "rb") as f:
            file_data = f.read()
        
        # 2. 计算文件信息
        file_size = len(file_data)
        file_md5 = hashlib.md5(file_data).hexdigest()
        
        # 3. 生成加密key（AES-128）
        aes_key = os.urandom(16)  # 16字节 = 128位
        
        # 4. 获取上传URL
        upload_req = {
            "filekey": os.path.basename(file_path),
            "media_type": 1,  # UploadMediaType.IMAGE
            "to_user_id": to_user_id,
            "rawsize": file_size,
            "rawfilemd5": file_md5,
            "filesize": file_size,  # 简化：假设不加密
            "aeskey": base64.b64encode(aes_key).decode('utf-8')
        }
        
        # 调用 getUploadUrl API
        upload_resp = self.api_client.get_upload_url_api(upload_req, bot_token)
        
        return {
            "upload_param": upload_resp.get("upload_param"),
            "aes_key": aes_key,
            "file_size": file_size
        }
    
    def build_image_message(self, to_user_id: str, context_token: str, 
                       upload_info: Dict[str, Any], caption: str = "") -> Dict[str, Any]:
        """
        构建图片消息
        """
        import uuid
        
        msg = {
            "from_user_id": "",
            "to_user_id": to_user_id,
            "client_id": f"img-{uuid.uuid4().hex[:8]}",
            "message_type": MessageType.BOT,
            "message_state": MessageState.FINISH,
            "context_token": context_token,
            "item_list": [
                {
                    "type": 2,  # MessageItemType.IMAGE
                    "image_item": {
                        "media": {
                            "encrypt_query_param": upload_info["upload_param"],
                            "aes_key": base64.b64encode(upload_info["aes_key"]).decode('utf-8'),
                            "encrypt_type": 1
                        },
                        "mid_size": upload_info["file_size"]
                    }
                }
            ]
        }
        
        # 如果有文字说明，先发送文字消息
        if caption:
            msg["item_list"].insert(0, {
                "type": 1,  # MessageItemType.TEXT
                "text_item": {"text": caption}
            })
        
        return {"msg": msg}
    

    def send_image_message(self, to_user_id: str, image_path: str,  bot_token: str,
                      context_token: str, caption: str = "") -> Optional[str]:
        """
        发送图片消息
        """
        try:
            # 1. 检查文件是否存在
            if not os.path.exists(image_path):
                print(f"❌ 图片文件不存在: {image_path}")
                return None
            
            # 2. 上传图片到CDN
            print(f"📤 上传图片: {image_path}")
            upload_info = self.cndManager.upload_media(bot_token, image_path, to_user_id, MessageItemType.IMAGE.value)
            
            if not upload_info.get("encrypt_query_param"):
                print("❌ 获取上传URL失败")
                return None
            
            # 3. 构建图片消息
            print("📝 构建图片消息...")
            msg_data = self.build_image_message(to_user_id, context_token, upload_info, caption)
            
            # 4. 发送消息
            print("🚀 发送图片消息...")
            resp = self.api_client.send_message(msg_data, bot_token)
            
            if resp:
                print(f"✅ 图片发送成功")
                return msg_data["msg"]["client_id"]
            else:
                print(f"❌ 图片发送失败")
                return None
                
        except Exception as e:
            print(f"❌ 发送图片异常: {e}")
            import traceback
            traceback.print_exc()
            return None