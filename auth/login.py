"""微信扫码登录模块"""
import time
import base64
import qrcode
import os
from typing import Optional, Dict, Any, Tuple
from PIL import Image
from io import BytesIO

from api.client import WeixinApiClient

from .storage import AccountStorage

class WeixinLogin:
    """微信登录管理器"""
    
    def __init__(self, base_url: str = "https://ilinkai.weixin.qq.com"):
        self.api_client = WeixinApiClient(base_url)
        self.storage = AccountStorage()
    
    def fetch_qrcode(self) -> Optional[Dict[str, Any]]:
        """
        获取登录二维码
        """
        try:
            data = self.api_client.get_qrcode()
            
            if data.get("ret") != 0:
                print(f"获取二维码失败: {data.get('err_msg', '未知错误')}")
                return None
            
            return {
                "qrcode": data.get("qrcode"),
                "qrcode_img_content": data.get("qrcode_img_content"),
                "session_key": data.get("session_key"),
            }
            
        except Exception as e:
            print(f"获取二维码异常: {e}")
            return None
    
    def display_qrcode(self, qrcode_img_content: str, save_path: str = "./login-qrcode.png") -> str:
        """
        显示并保存二维码
        """
        try:
            if not qrcode_img_content:
                print("❌ 二维码URL为空")
                return ""
            
            print(f"二维码链接: {qrcode_img_content}")
            print("正在生成二维码图片...")
            
            # 1. 使用 qrcode 库生成二维码
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qrcode_img_content)
            qr.make(fit=True)
            
            # 2. 生成二维码图片
            img = qr.make_image(fill_color="black", back_color="white")
            
            
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 4. 保存二维码图片
            with open(save_path, "wb") as f:
                img.save(f)  # ✅ 传递文件对象，而不是字符串
            print(f"✅ 二维码已生成并保存: {save_path}")
            
            # 5. 尝试显示图片
            try:
                img.show()
                print("二维码图片已显示")
            except:
                print(f"请手动打开文件扫描: {save_path}")
            
            print(f"\n📱 请用微信扫描此二维码登录")
            return save_path
            
        except Exception as e:
            print(f"❌ 生成二维码失败: {e}")
            return ""
    
    def poll_qr_status(self, qrcode: str, timeout: int = 300) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        轮询二维码状态
        返回: (是否成功, 账号数据)
        """
        print("等待扫码确认...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                data = self.api_client.get_qrcode_status(qrcode)
                
                status = data.get("status")
                print(f"扫码状态: {status}")
                
                if status == "confirmed":
                    bot_token = data.get("bot_token")
                    ilink_bot_id = data.get("ilink_bot_id")
                    ilink_user_id = data.get("ilink_user_id")
                    
                    if bot_token and ilink_bot_id:
                        print(f"✅ 登录成功!")
                        return True, {
                            "bot_token": bot_token,
                            "ilink_bot_id": ilink_bot_id,
                            "ilink_user_id": ilink_user_id,
                            "base_url": self.api_client.base_url
                        }
                
                elif status == "expired":
                    print("二维码已过期")
                    return False, None
                
                elif status == "scanned":
                    print("✅ 已扫码，请在手机上确认登录")
                
                time.sleep(3)
                
            except Exception as e:
                print(f"轮询状态异常: {e}")
                time.sleep(5)
        
        print("登录超时")
        return False, None
    
    def login_flow(self) -> bool:
        """
        完整的扫码登录流程
        """
        print("=== 微信扫码登录 ===")
        
        # 1. 获取二维码
        qrcode_info = self.fetch_qrcode()
        if not qrcode_info:
            return False
        
        qrcode = qrcode_info.get("qrcode")
        qrcode_img = qrcode_info.get("qrcode_img_content")
        
        if not qrcode or not qrcode_img:
            return False
        
        # 2. 显示二维码
        qr_path = self.display_qrcode(qrcode_img)
        
        # 3. 轮询扫码状态
        success, account_data = self.poll_qr_status(qrcode)
        
        if success and account_data:
            # 4. 保存账号数据
            self.storage.save_account(account_data)
            return True
        
        return False