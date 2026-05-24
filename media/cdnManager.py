import hashlib
import os
import time
import requests
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad
from api.types import MessageItemType


class CDNManager:

    BASE_URL = "https://ilinkai.weixin.qq.com"

    def __init__(self,save_dir="./downloads", timeout=120):
        self.save_dir = save_dir
        self.timeout = timeout
        os.makedirs(self.save_dir, exist_ok=True)

    def _parse_aes_key(self, aes_key_base64: str) -> bytes:
        """
        官方 parseAesKey 逻辑：
        - Base64 解码
        - 如果是 16 字节 → 直接返回
        - 如果是 32 字节且是十六进制字符串 → 再 hex 解码为 16 字节
        """
        decoded = base64.b64decode(aes_key_base64)
        if len(decoded) == 16:
            return decoded
        elif len(decoded) == 32:
            # 尝试将解码结果解释为十六进制字符串
            hex_str = decoded.decode('ascii')
            if all(c in '0123456789abcdefABCDEF' for c in hex_str):
                return bytes.fromhex(hex_str)
        raise ValueError(f"无法解析 aes_key: 解码后长度为 {len(decoded)}")

    def download_image(self, image_item, save_path=None):
        """
        根据官方实现下载并解密微信图片
        """
        # 1. 提取字段
        # 优先使用外层的 aeskey（32位十六进制字符串）
        outer_aeskey_hex = image_item.get('aeskey')
        inner_aes_key_b64 = image_item['media']['aes_key']
        
        # 官方代码：如果外层存在，将 hex 转成 base64 再解析；否则直接用内层的 base64
        if outer_aeskey_hex:
            # 外层是 32 个十六进制字符（16字节），先转 bytes 再转 base64 字符串
            outer_key_bytes = bytes.fromhex(outer_aeskey_hex)
            aes_key_base64 = base64.b64encode(outer_key_bytes).decode('ascii')
        else:
            aes_key_base64 = inner_aes_key_b64
        
        # 2. 解析出真正的 AES 密钥（16字节）
        aes_key = self._parse_aes_key(aes_key_base64)
        
        # 3. 下载加密数据（直接用 full_url，官方是用 encrypt_query_param 构建，但结果相同）
        url = image_item['media']['full_url']
        resp = requests.get(url, timeout=self.timeout)
        resp.raise_for_status()
        encrypted_data = resp.content
        
        # 4. AES-128-ECB 解密
        cipher = AES.new(aes_key, AES.MODE_ECB)
        decrypted_padded = cipher.decrypt(encrypted_data)
        
        # 5. 去除 PKCS7 填充（块大小 16 字节）
        decrypted_data = unpad(decrypted_padded, AES.block_size)
        
        # 6. 校验图片头（可选）
        if not (decrypted_data.startswith(b'\xff\xd8\xff') or decrypted_data.startswith(b'\x89PNG')):
            print("警告：解密后的数据不是 JPEG/PNG 格式，可能解密失败")
        
        # 7. 保存图片
        if save_path is None:
            taskid = url.split('taskid=')[-1] if 'taskid=' in url else None
            filename = f"{taskid}.jpg" if taskid else f"wechat_image_{int(time.time()*1000)}.jpg"
            save_path = os.path.join(self.save_dir, filename)
        
        with open(save_path, 'wb') as f:
            f.write(decrypted_data)
        
        return save_path
    
    @staticmethod
    def _get_uin() -> str:
        """生成一个随机的 UIN（用户标识）"""
        return str(int(time.time() * 1000)) + str(os.getpid())
    
    def _get_upload_info(self, token: str, to_user_id: str, filekey: str, raw_size: int, raw_md5: str, media_type: int) -> dict:
        """获取上传所需的参数和AES密钥"""
        url = f"{self.BASE_URL}/ilink/bot/getuploadurl"
        headers = {
            "Authorization": f"Bearer {token}",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": self._get_uin(), # 生成随机UIN的方法
            "Content-Type": "application/json"
        }
        
        payload = {
            "filekey": filekey,
            "media_type": media_type,
            "to_user_id": to_user_id,
            "rawsize": raw_size,
            "rawfilemd5": raw_md5,
            "filesize": raw_size # 加密后文件尺寸会变，此处暂填原大小，实际应以加密后为准。
        }
        
        # 发起POST请求...
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        data = response.json()
        print(f"_get_upload_info response: {data}")
        return {
            "upload_param": data["upload_param"],
            "aes_key": base64.b64decode(data["aes_key"])
        }
    

    @staticmethod
    def _encrypt_aes_ecb(plaintext: bytes, key: bytes) -> bytes:
        """
        使用 AES-128-ECB 模式加密数据，采用 PKCS7 填充（块大小 16 字节）
        """
        cipher = AES.new(key[:16], AES.MODE_ECB)
        # 使用 pad 函数进行填充
        padded_data = pad(plaintext, AES.block_size)  # AES.block_size = 16
        return cipher.encrypt(padded_data)
    
    def _upload_to_cdn(self, upload_param: str, ciphertext: bytes) -> str:
        """将加密数据上传至微信CDN，并返回解密所需的加密查询参数"""
        cdn_url = f"https://novac2c.cdn.weixin.qq.com/c2c/upload?{upload_param}"
        headers = {"Content-Type": "application/octet-stream"}
        response = requests.put(cdn_url, data=ciphertext, headers=headers)
        # 从响应头中获取用于下载解密的加密查询参数
        encrypted_query_param = response.headers.get("x-encrypted-param")
        return encrypted_query_param if encrypted_query_param else ""
    
    def upload_media(self, token: str, file_path: str, to_user_id: str, media_type: int, **kwargs) -> dict:
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
        upload_info = self._get_upload_info(token, to_user_id, filekey, raw_size, raw_md5, media_type)
        
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
        if media_type == MessageItemType.VIDEO.value: # 视频
            # 需要先提取视频第一帧作为缩略图并上传
            # 然后调用_get_upload_info获取缩略图上传信息
            # 这里简化处理，理想情况需要实现类似逻辑[reference:4]
            # 视频消息还需携带时长(秒)
            media_info["duration"] = kwargs.get("duration", 0)
            # 添加缩略图信息
            # media_info["thumb_info"] = {...}

        # 针对普通文件，需要指定文件名
        if media_type == MessageItemType.FILE.value: # 文件
            media_info["file_name"] = kwargs.get("fileName", filekey)

        return media_info
