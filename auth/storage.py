"""账号数据存储管理"""
import json
import os
import time
from typing import Optional, Dict, Any, List

from api.types import AccountData


class AccountStorage:
    """账号存储管理器"""
    
    def __init__(self, base_dir: str = "./"):
        self.base_dir = base_dir
        self.temp_dir = os.path.join(base_dir, "temp")
        self.account_dir = os.path.join(base_dir, "accounts")
        
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.account_dir, exist_ok=True)
    
    def _normalize_account_id(self, ilink_bot_id: str) -> str:
        """规范化账号ID（替换特殊字符）"""
        return ilink_bot_id.replace('@', '-').replace('.', '-')
    
    def save_account(self, account_data: Dict[str, Any]) -> str:
        """
        保存账号数据
        """
        ilink_bot_id = account_data.get("ilink_bot_id")
        if not ilink_bot_id:
            raise ValueError("无效的账号ID")
        
        normalized_id = self._normalize_account_id(ilink_bot_id)
        
        # 构建完整账号数据
        account = AccountData(
            account_id=normalized_id,
            bot_token=account_data.get("bot_token", ""),
            ilink_bot_id=ilink_bot_id,
            ilink_user_id=account_data.get("ilink_user_id", ""),
            base_url=account_data.get("base_url", ""),
            saved_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        
        # 保存账号文件
        account_file = os.path.join(self.account_dir, f"{normalized_id}.json")
        with open(account_file, "w", encoding="utf-8") as f:
            json.dump(account.to_dict(), f, indent=2, ensure_ascii=False)
        
        # 更新账号索引
        self._update_account_index(normalized_id)
        
        print(f"✅ 账号数据已保存: {account_file}")
        return normalized_id
    
    def _update_account_index(self, account_id: str) -> None:
        """更新账号索引"""
        index_file = os.path.join(self.account_dir, "accounts.json")
        account_ids = []
        
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                try:
                    account_ids = json.load(f)
                except:
                    pass
        
        if account_id not in account_ids:
            account_ids.append(account_id)
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(account_ids, f, indent=2, ensure_ascii=False)
    
    def load_account(self, account_id: Optional[str] = None) -> Optional[AccountData]:
        """
        加载账号数据
        """
        if not account_id:
            # 尝试加载第一个账号
            index_file = os.path.join(self.account_dir, "accounts.json")
            if os.path.exists(index_file):
                with open(index_file, "r", encoding="utf-8") as f:
                    try:
                        account_ids = json.load(f)
                        if account_ids:
                            account_id = account_ids[0]
                    except:
                        pass
        
        if not account_id:
            return None
        
        account_file = os.path.join(self.account_dir, f"{account_id}.json")
        if not os.path.exists(account_file):
            return None
        
        try:
            with open(account_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return AccountData.from_dict(data)
            
        except Exception as e:
            print(f"加载账号失败: {e}")
            return None
    
    def list_accounts(self) -> List[str]:
        """列出所有账号ID"""
        index_file = os.path.join(self.account_dir, "accounts.json")
        if not os.path.exists(index_file):
            return []
        
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []