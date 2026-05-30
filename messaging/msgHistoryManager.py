import json
import time
import threading
import os
import tempfile


class MsgHistoryManager:
    """
    消息历史管理器
    用于存储和管理会话历史
    消息按收到/发送的时间 分别存到./history/目录下对应日期的json文件中
    """
    def __init__(self, type='wx'):
        # 每个历史文件对应一个Lock，防止多线程写入冲突（进程内安全）
        self.type = type
        self._locks = {}
        self._locks_lock = threading.Lock()
    
    def _get_lock_for(self, filepath: str) -> threading.Lock:
        """返回给定文件路径对应的Lock，如果不存在则创建。"""
        with self._locks_lock:
            lock = self._locks.get(filepath)
            if lock is None:
                lock = threading.Lock()
                self._locks[filepath] = lock
            return lock
        
    def _dir_path(self) -> str:
        """返回历史记录目录路径"""
        path = os.path.join('.', f'history/{self.type}')
        return path
    

    def save_model_messages(self, messages: list, session: str):
        """保存模型对话消息到历史记录（线程安全，原子写入）"""
        history_dir = self._dir_path()
        os.makedirs(history_dir, exist_ok=True)
        history_file = os.path.join(history_dir, f"{session}.json")

        lock = self._get_lock_for(history_file)
        with lock:
            # 直接覆盖
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
            print(f"模型消息已保存到 {history_file}")
    
    def load_model_messages(self, session: str) -> list:
        """加载模型对话消息历史（线程安全）"""
        history_dir = self._dir_path()
        history_file = os.path.join(history_dir, f"{session}.json")

        lock = self._get_lock_for(history_file)
        with lock:
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except FileNotFoundError:
                print(f"未找到历史记录文件 {history_file}")
                return []
            except json.JSONDecodeError:
                print(f"历史记录文件 {history_file} 格式错误")
                return []

    
    def save_message(self, msg_info: dict):
        """保存消息到历史记录（线程安全，原子写入）"""
        raw_msg = msg_info.get("raw_msg", {})
        if not msg_info:
            print(f"无效的消息数据 {msg_info}")
            return

        update_time_ms = raw_msg.get("update_time_ms", 0)
        if update_time_ms == 0:
            update_time_ms = int(time.time() * 1000)
        # 根据update_time_ms获取对应的历史记录json文件，如果文件不存在则新建
        update_time_sec = update_time_ms // 1000
        date_str = time.strftime("%Y-%m-%d", time.localtime(update_time_sec))
        history_dir = self._dir_path()
        history_file = os.path.join(history_dir, f"{date_str}.json")

        # 确保目录存在
        os.makedirs(history_dir, exist_ok=True)

        lock = self._get_lock_for(history_file)
        with lock:
            # 读取原来的内容，并追加，原来的内容格式是[msg_info...]
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except FileNotFoundError:
                history = []
            except json.JSONDecodeError:
                # 文件损坏或被部分写入，备份并重建
                try:
                    backup_path = history_file + ".corrupt"
                    os.replace(history_file, backup_path)
                except Exception:
                    pass
                history = []

            history.append(msg_info)

            # 原子写入：先写入临时文件，然后替换
            dir_for_tmp = os.path.dirname(history_file) or '.'
            fd, tmp_path = tempfile.mkstemp(dir=dir_for_tmp, prefix=".history_", suffix=".tmp")
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as tmpf:
                    json.dump(history, tmpf, ensure_ascii=False, indent=2)
                    tmpf.flush()
                    os.fsync(tmpf.fileno())
                # 替换到目标文件（原子操作）
                os.replace(tmp_path, history_file)
            finally:
                # 若临时文件仍存在，尝试删除
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    print(f"警告: 无法删除临时文件 {tmp_path}")


msgHistoryManager = MsgHistoryManager()

modelHistoryManager = MsgHistoryManager(type="model")
