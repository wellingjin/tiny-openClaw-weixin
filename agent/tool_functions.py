
import datetime
import json
import requests
from typing import Optional, Dict, Any


def get_current_datetime():
    """获取当前日期和时间"""
    result = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return json.dumps({"datetime": result})



def get_realtime_quotes(stock_codes: str) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    批量获取股票实时行情（腾讯财经接口）
    
    Args:
        stock_codes: 股票代码字符串，多个用逗号分隔。
            示例："sh600519,sz000001,hk00700,usAAPL"
    
    Returns:
        字典，键为原始股票代码（如 "sh600519"），值为行情数据字典（失败时为 None）
    """
    # 分割并清理代码
    codes_list = [code.strip() for code in stock_codes.split(',') if code.strip()]
    if not codes_list:
        return {}
    
    # 构建请求 URL
    codes_param = ','.join(codes_list)
    url = f"http://qt.gtimg.cn/q={codes_param}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    result = {}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        resp.encoding = 'gbk'
        raw_text = resp.text.strip()
        
        # 按分号分割各股票数据，最后可能有一个空字符串
        records = raw_text.split(';')
        for record in records:
            record = record.strip()
            if not record or '="' not in record:
                continue
            
            # 提取变量名（如 v_sh600519）和数据部分
            # 格式：v_sh600519="..."
            eq_idx = record.find('="')
            if eq_idx == -1:
                continue
            var_part = record[:eq_idx]  # v_sh600519
            data_part = record[eq_idx+2:-1]  # 去掉前导 =" 和结尾的 "（最后一个字符是引号）
            
            # 变量名以 "v_" 开头，去掉前两个字符得到代码
            if not var_part.startswith('v_'):
                continue
            stock_code = var_part[2:]  # 例如 "sh600519"
            
            fields = data_part.split('~')
            if len(fields) < 45:
                result[stock_code] = None
                continue
            
            # 解析基本字段
            quote = {
                "market": fields[0],
                "code": fields[2],
                "name": fields[1],
                "latest": float(fields[3]) if fields[3] else None,
                "yesterday_close": float(fields[4]) if fields[4] else None,
                "open": float(fields[5]) if fields[5] else None,
                "volume": int(float(fields[6])) * 100 if fields[6] else None,  # 手 → 股
                "high": float(fields[33]) if fields[33] else None,
                "low": float(fields[34]) if fields[34] else None,
                "change": float(fields[31]) if fields[31] else None,
                "change_percent": float(fields[32]) if fields[32] else None,
                "turnover": float(fields[37]) if fields[37] else None,  # 万元
                "volume_ratio": float(fields[43]) if len(fields) > 43 and fields[43] else None,
                "update_time": fields[30] if len(fields) > 30 else None,
            }
            
            # 移除 None 值
            quote = {k: v for k, v in quote.items() if v is not None}
            result[stock_code] = quote
    
    except Exception as e:
        print(f"批量获取行情失败: {e}")
        for code in codes_list:
            result[code] = None
    
    return result

def get_quotes_info(stock_codes: str) -> str:
    """返回 JSON 字符串"""
    data = get_realtime_quotes(stock_codes)
    return json.dumps(data, ensure_ascii=False, indent=2)

# 测试
if __name__ == "__main__":
    print(get_quotes_info("sh600519,sz000001"))