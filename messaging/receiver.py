"""消息接收模块"""
import json
import time
from typing import Optional, Dict, Any, Callable

from api.client import WeixinApiClient
from api.types import MessageItemType

class Message:
    """消息数据结构"""
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.from_user = data.get("from_user_id", "")
        self.item_list = data.get("item_list", [])
        self.msg_type = data.get("message_type", "")
        self.create_time_ms = data.get("create_time_ms", 0)
        self.seq = data.get("seq", -1)
        self.message_id = data.get("message_id", "")

    def get_text(self) -> Optional[str]:
        """获取消息文本内容"""
        for item in self.item_list:
            if item.get("type") == MessageItemType.TEXT:
                return item.get("text_item", {}).get("text","")

class MessageReceiver:
    """消息接收器"""
    
    def __init__(self, api_client: WeixinApiClient, bot_token: str):
        self.api_client = api_client
        self.bot_token = bot_token
        self.get_updates_buf: str = ""
    
    def receive_messages(self, timeout_ms: int = 35000) -> Optional[Dict[str, Any]]:
        """
        接收消息
        """
        try:
            result = self.api_client.get_updates(
                get_updates_buf=self.get_updates_buf,
                token=self.bot_token,
                timeout_ms=timeout_ms
            )
        
        # {'msgs': [{'seq': 2, 'message_id': 7441725234877553672, 'from_user_id': 'o9cq805o_B3ZYI_XRrQaWSHwlCDk@im.wechat', 'to_user_id': '43a25d7f293c@im.bot', 'client_id': 'mmassistant_bypmsg_inbox_e96375268491755f2234fbcb22a7f2dbmmo9cq80zdwoFUiXYHJ2QBGagzvY0g@weclaw_2_1774245554', 'create_time_ms': 1774245556513, 'update_time_ms': 1774245556619, 'delete_time_ms': 0, 'session_id': '', 'group_id': '', 'message_type': 1, 'message_state': 2, 'item_list': [{'type': 1, 'create_time_ms': 1774245556513, 'update_time_ms': 1774245556513, 'is_completed': True, 'text_item': {'text': 'ai'}}], 'context_token': 'AARzJWAFAAABAAAAAADyysYymBCegTpqtNbAaSAAAAB+9905Q6UiugPBawU3n3cyzQX+LkN8ofRzsCZYN0mt7n8VaMj9omF7OEokDxjqA00Egerjz8Nu9aj8AvzqZQ71uTeu9iCC'}], 'sync_buf': 'CAIQluSaytEzGPbjmsrRMw==', 'get_updates_buf': 'ChAIAhCW5JrK0TMY9uOaytEzEjo0M2EyNWQ3ZjI5M2NAaW0uYm90OjA2MDAwMDllMTI1MjBlODE1MTNkOGE4Yzg5NWY5NmYwMTdjMTNj'}
            contents = result.get("msgs", [])
            if len(contents) > 0:
                return result
            else:
                err_msg = result.get("err_msg", "empty message")
                print(f"获取消息失败: {err_msg}")
                return None
                
        except Exception as e:
            print(f"接收消息异常: {e}")
            return None
    
    def extract_message_info(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取消息信息
        """
        from_user_id = msg.get("from_user_id", "")
        context_token = msg.get("context_token", "")
        item_list = msg.get("item_list", [])
        
        content_type = "unknown"
        content = ""
        
        for item in item_list:
            item_type = item.get("type")
            
            if item_type == MessageItemType.TEXT.value:
                content_type = "text"
                text_item = item.get("text_item", {})
                content = text_item.get("text", "")
                break
            elif item_type == MessageItemType.IMAGE.value:
                content_type = "image"
                content = "图片消息"
                break
            elif item_type == MessageItemType.VIDEO.value:
                content_type = "video"
                content = "视频消息"
                break
            elif item_type == MessageItemType.FILE.value:
                content_type = "file"
                content = "文件消息"
                break
        
        return {
            "from_user_id": from_user_id,
            "context_token": context_token,
            "content_type": content_type,
            "content": content,
            "raw_msg": msg
        }