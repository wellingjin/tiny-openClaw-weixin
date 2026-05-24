"""命令行入口"""
import json
import sys
import time
from typing import Optional
from agent.ToolAgent import ToolAgent
from api.client import WeixinApiClient
from api.types import AccountData
from auth.login import WeixinLogin
from media.cdnManager import CDNManager
from messaging.msgHistoryManager import msgHistoryManager
from messaging.receiver import MessageReceiver
from messaging.sender import MessageSender
from auth.storage import AccountStorage

class WeixinBot:
    """微信机器人主类"""
    
    def __init__(self):
        self.account: Optional[AccountData] = None
        self.api_client: Optional[WeixinApiClient] = None
        self.login_manager: Optional[WeixinLogin] = None
        self.storage = AccountStorage()
        self.sender: Optional[MessageSender] = None
        self.receiver: Optional[MessageReceiver] = None
        self.cndManager = CDNManager()
        self.msgHistoryManager = msgHistoryManager
        self.agent = ToolAgent()     
        
        # 上下文Token缓存
        self.context_token_cache: dict = {}
    
    def set_context_token(self, user_id: str, context_token: str) -> None:
        """设置上下文Token"""
        self.context_token_cache[user_id] = context_token
    
    def get_context_token(self, user_id: str) -> Optional[str]:
        """获取上下文Token"""
        return self.context_token_cache.get(user_id)
    
    def initialize(self) -> bool:
        """初始化机器人"""
        # 尝试加载已有账号
        self.account = self.storage.load_account()
        
        if not self.account:
            print("未找到已登录账号，需要扫码登录")
            return False
        
        # 初始化API客户端
        self.api_client = WeixinApiClient(self.account.base_url)
        
        # 初始化登录管理器
        self.login_manager = WeixinLogin(self.account.base_url)
        
        # 初始化消息处理器
        self.sender = MessageSender(self.api_client)
        self.receiver = MessageReceiver(self.api_client, self.account.bot_token)
        
        print(f"✅ 已加载账号: {self.account.ilink_bot_id}")
        return True
    
    def login(self) -> bool:
        """执行登录流程"""
        if not self.login_manager:
            self.login_manager = WeixinLogin()
        
        success = self.login_manager.login_flow()
        
        if success:
            # 重新加载账号
            self.account = self.storage.load_account()
            if self.account:
                self.api_client = WeixinApiClient(self.account.base_url)
                self.receiver = MessageReceiver(self.api_client, self.account.bot_token)
                self.sender = MessageSender(self.api_client)
                return True
        
        return False
    
    def process_message(self, msg_info: dict) -> None:
        """处理消息"""
        from_user_id = msg_info["from_user_id"]
        context_token = msg_info["context_token"]
        content_type = msg_info["content_type"]
        content = msg_info["content"]
        print(f"收到消息: \n{json.dumps(msg_info, ensure_ascii=False)}")
        self.msgHistoryManager.save_message(msg_info)
        
        # 保存上下文Token
        self.set_context_token(from_user_id, context_token)
        
        if content_type == "text" and content:
            print(f"\n📨 收到消息来自 {from_user_id}:")
            print(f"{content}")
            
            # 发送自动回复
            if self.sender and self.account:
                question = self.agent.ask(content)
                message_id = self.sender.send_text(
                            from_user_id, question if question else "无法处理该问题", context_token, self.account.bot_token
                        )
                if message_id:
                    print(f"   💬 已自动回复")
        elif content_type == "image":
            raw_msg = msg_info.get("raw_msg", {})
            item_list = raw_msg.get("item_list", [])
            file_item = item_list[0] if item_list else {}
            image_item = file_item.get("image_item", {})
            try:
                saved_path = self.cndManager.download_image(image_item)
                print(f"\n🖼️ 收到图片来自 {from_user_id}, 已保存至: {saved_path}")
                if self.sender and self.account:
                    # self.sender.send_image_message(from_user_id, saved_path, context_token, self.account.bot_token)
                    message_id = self.sender.send_text(
                            from_user_id, "图片已保存到NAS服务中", context_token, self.account.bot_token
                        )
            except Exception as e:
                print(f"   ❌ 图片下载失败: {e}")
        else:
            print(f"\n📨 收到{content_type}消息来自 {from_user_id}")
    
    def start_message_loop(self, interval: float = 1.0) -> None:
        """启动消息监听循环"""
        if not self.receiver or not self.account:
            print("❌ 未初始化，无法启动消息循环")
            return
        
        print(f"\n🚀 开始监听消息，按 Ctrl+C 停止...")
        empty_count = 0
        
        try:
            while True:
                result = self.receiver.receive_messages()
                
                if result and "msgs" in result:
                    msgs = result.get("msgs", [])
                    if msgs:
                        empty_count = 0
                        for msg in msgs:
                            msg_info = self.receiver.extract_message_info(msg)
                            self.process_message(msg_info)
                    else:
                        empty_count += 1
                        if empty_count % 10 == 0:
                            print(f"⏳ 等待消息中... ({empty_count}次空轮询)")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n👋 停止消息监听")
        except Exception as e:
            print(f"\n❌ 消息循环异常: {e}")
    
    def run(self) -> None:
        """运行机器人"""
        print("=== 微信 iLink 协议机器人 ===")
        print("基于 @tencent-weixin/openclaw-weixin 插件实现")
        
        # 初始化
        if not self.initialize():
            # 需要登录
            if not self.login():
                print("登录失败，程序退出")
                sys.exit(1)
        
        # 启动消息循环
        self.start_message_loop()

if __name__ == "__main__":
    bot = WeixinBot()
    bot.run()