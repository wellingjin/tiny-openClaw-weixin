#!/usr/bin/env python3
"""
极简 ToolAgent —— 无需配置，开箱即用。
用法：
    agent = ToolAgent()
    answer = agent.ask("北京天气怎么样？")
    print(answer)
"""

import datetime
import json
import inspect
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Callable, Dict, List, Optional
from ollama import chat, Client


class ToolAgent:
    """零配置工具调用智能体，内置常用工具，也可自行扩展。"""

    def __init__(self, model: str = "qwen3:0.6b"):
        """
        参数 model 可选，默认使用 qwen3:0.6b（你已下载的模型）。
        如果你希望完全无参，可以忽略这个参数，类内部固定模型名。
        """
        self.model = model
        self._tools: Dict[str, Callable] = {}
        self._tool_defs: List[Dict] = []
        self.systemPrompt = {"role": "system", "content": "你是我的智能助手，可以调用工具函数来获取信息或执行任务。"}
        self.messages = [self.systemPrompt]
        # 自动注册内置工具
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """注册内置的天气查询和数学计算工具。"""
        self.register_tool(self._calculate)
        self.register_tool(self._get_current_datetime)
        self.register_tool(self._get_weather)
        self.register_tool(self._fetch_webpage_content)
        

    def register_tool(self, func: Callable) -> None:
        """注册一个工具函数，函数名、参数、docstring 会自动解析。"""
        # 构建 Ollama 需要的 tool 定义
        tool_def = self._build_tool_definition(func)
        self._tool_defs.append(tool_def)
        self._tools[func.__name__] = func

    def _build_tool_definition(self, func: Callable) -> Dict:
        """从函数签名和 docstring 生成 tool 定义（JSON Schema 子集）。"""
        sig = inspect.signature(func)
        props = {}
        required = []
        for name, param in sig.parameters.items():
            if param.default == inspect.Parameter.empty:
                required.append(name)
            # 简单类型推断，可根据需要扩展
            param_type = "string"
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            props[name] = {
                "type": param_type,
                "description": f"参数 {name}"   # 可从 docstring 提取更详细的描述，此处简化
            }
        doc = inspect.getdoc(func) or ""
        description = doc.split("\n")[0] if doc else f"函数 {func.__name__}"
        return {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            },
        }

    def _execute_tool(self, tool_call) -> str:
        """执行模型请求的工具调用，返回结果的 JSON 字符串。"""
        name = tool_call.function.name
        args = tool_call.function.arguments
        if name not in self._tools:
            return json.dumps({"error": f"未知工具: {name}"})
        try:
            result = self._tools[name](**args)
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False)
            return result
        except Exception as e:
            return json.dumps({"error": f"执行 {name} 时出错: {str(e)}"})

    def ask(self, question: str, max_turns: int = 3) -> str:
        """
        用户唯一需要调用的方法：传入问题，返回回答（字符串）。
        内部会自动判断是否需要调用工具，并返回最终结果。
        """
        if len(self.messages) > 50:
            # 删除前两个
            self.messages = self.messages[1:]
            self.messages[0] = self.systemPrompt

        self.messages.append({"role": "user", "content": question})
                    
        for _ in range(max_turns):
            print(f'正在与模型交互...')
            response = chat(
                model=self.model,
                messages=self.messages,
                tools=self._tool_defs if self._tool_defs else None,
            )
            print(f"Response: {response.message}")
            if not response.message.tool_calls:
                question = response.message.content if response.message.content else "这个问题难住我了"
                self.messages.append({"role": "assistant", "content": question})
                return question
                
            # 处理工具调用（只处理第一个，简化）
            tool_result = self._execute_tool(response.message.tool_calls[0])
            
            self.messages.append(response.message)
            self.messages.append({"role": "tool", "content": tool_result})
        return "达到最大调用轮数，未获得最终回答。"

    # ---------- 内置工具实现（使用免费 wttr.in 和简单 eval） ----------
    @staticmethod
    def _get_current_datetime() -> Dict:
        """
        获取当前的日期和时间。

        当用户询问当前时间、日期、星期、几月几号等问题时，必须调用此函数。

        
        Returns:
            dict: 包含当前日期、时间、星期、时区等信息的字典。
        """
        now = datetime.datetime.now()
        weekday_map = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekday_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        
        # 根据用户可能需要的格式返回多种信息
        print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        return {
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "weekday_en": weekday_map[now.weekday()],
            "weekday_cn": weekday_cn[now.weekday()],
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
            "timezone": 'local',
            "timestamp": int(now.timestamp())
        }

    

    @staticmethod
    def _fetch_webpage_content(url: str, max_retries: int = 3) -> dict:
        """
        获取任意公开网页的主体内容（支持微信公众号文章等）。

        Args:
            url: 网页URL，例如 https://mp.weixin.qq.com/s/...
            max_retries: 最大重试次数，默认为3

        Returns:
            dict: 包含以下字段：
                - url: 原始URL
                - title: 页面标题
                - content: 清洗后的纯文本正文
                - success: 是否成功获取
                - error: 失败时的错误信息（如果有）
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        for attempt in range(max_retries):
            try:
                # 发送GET请求，设置超时时间为10秒
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()  # 如果不是200状态码，则抛出异常

                # 使用BeautifulSoup解析HTML
                soup = BeautifulSoup(response.text, 'html.parser')

                # 提取标题
                title = soup.find('title').get_text().strip() if soup.find('title') else ''

                # 移除无用的脚本和样式
                for script in soup(['script', 'style', 'nav', 'footer', 'aside']):
                    script.decompose()

                # 尝试提取正文内容（优先选择常见正文容器）
                content = ''
                article_selectors = ['article', 'div.rich_media_content', 'div.content', 'div.post-content', 'main', '.article-content']

                for selector in article_selectors:
                    article = soup.select_one(selector)
                    if article:
                        content = article.get_text(separator='\n', strip=True)
                        break

                # 如果没找到特定容器，则回退到body
                if not content and soup.body:
                    content = soup.body.get_text(separator='\n', strip=True)

                # 进一步清洗：压缩多余空行
                content = '\n'.join(line.strip() for line in content.splitlines() if line.strip())

                return {
                    'url': url,
                    'title': title,
                    'content': content,
                    'success': True
                }

            except requests.exceptions.RequestException as e:
                error_msg = f'请求失败 (尝试 {attempt+1}/{max_retries}): {str(e)}'
                if attempt == max_retries - 1:
                    return {'url': url, 'title': '', 'content': '', 'success': False, 'error': error_msg}
            except Exception as e:
                return {'url': url, 'title': '', 'content': '', 'success': False, 'error': f'解析失败: {str(e)}'}

        # 正常情况下不会执行到这里
        return {'url': url, 'title': '', 'content': '', 'success': False, 'error': '未知错误'}

    @staticmethod
    def _get_weather(city: str) -> Dict:
        """
        获取指定城市的实时天气。
        Args:
            city: 需要查询天气的城市名称。

        Returns:
            包含天气信息的字典。
        """
        url = f"https://wttr.in/{city}?format=j1"
        try:
            print(f"查询天气: {city}")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            current = data["current_condition"][0]
            unit: str = "celsius"
            if unit == "celsius":
                temp = current["temp_C"]
            else:
                temp = current["temp_F"]
            condition = current["weatherDesc"][0]["value"]
            return {
                "city": city,
                "temperature": temp,
                "unit": unit,
                "condition": condition,
                "humidity": current["humidity"],
                "wind_speed": current["windspeedKmph"]
            }
        except Exception as e:
            return {"error": f"天气查询失败: {str(e)}"}

    @staticmethod
    def _calculate(expression: str) -> Dict:
        """
        计算数学表达式。
        Args:
            expression: 数学表达式的字符串。

        Returns:
            运算的结果对应的json。
        """
        # 注意：eval 有安全风险，仅用于受控环境
        try:
            # 限制允许的字符和运算，避免恶意代码
            print(f"计算表达式: {expression}")
            allowed = set("0123456789+-*/(). ")
            if not all(c in allowed for c in expression):
                return {"error": "表达式包含非法字符"}
            result = eval(expression)
            return {"result": result}
        except Exception as e:
            return {"error": f"计算失败: {str(e)}"}


# ==================== 使用示例 ====================
if __name__ == "__main__":
    agent = ToolAgent()                     # 无需任何参数！
    while True:
        q = input("\n请输入问题（输入 q 退出）: ").strip()
        if q.lower() == 'q':
            break
        answer = agent.ask(q)
        print(f"🤖 {answer}")