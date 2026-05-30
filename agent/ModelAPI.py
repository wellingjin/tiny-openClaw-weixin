import datetime
import os
import json
from pyexpat.errors import messages
import requests
from openai import OpenAI
from openai.types.chat.completion_create_params import WebSearchOptions
from agent.tool_functions import get_current_datetime, get_quotes_info
from messaging.msgHistoryManager import modelHistoryManager




class ModelAPI:
    """模型API调用封装"""
    def __init__(self, scene: str):
        self.scene = scene
        self.model_config = {}
        self.scene_config = {}
        self.tools = []
        self.load_config(scene)
        if not self.model_config or not self.scene_config:
            raise ValueError("配置加载失败")
        
        self.model = self.scene_config.get("model", "")
        supported_models = self.model_config.get("supported_models", [])
        if self.model not in supported_models:
            raise ValueError(f"模型 {self.model} 不被支持")
        
        function_names = self.scene_config.get("tools", [])
        tools = []
        for tool_name in function_names:
            tools.append(self.tools[tool_name])
        self.tools = tools
        self.system_prompt = self.scene_config.get("system_prompt", "")
        self.api_key = self.model_config.get("api_key", "")
        base_url = self.model_config.get("base_url", "")

        self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=base_url
                )

        
    
    def load_config(self, scene: str):
        """加载配置"""
        # 从./accounts/model_api.json加载配置
        config_path = os.path.join(os.path.dirname(__file__), "..", "accounts", "model_api.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.scene_config = config.get(scene, {})
                owned_by = self.scene_config.get("owned_by", "")
                if not owned_by:
                    raise ValueError("模型所属者不能为空")
                all_model_config = config.get("model_config", {})
                self.model_config = all_model_config.get(owned_by, {})
                self.tools = config.get("tools", [])
        else:
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

    def query_balance(self) -> str:
        """查询余额"""
        url = self.model_config.get("query_balance_url", "")
        if not url:
            return "未配置查询余额的URL"

        payload={}
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

        response = requests.request("GET", url, headers=headers, data=payload)
        if response.status_code != 200:
            return f"查询失败: {response.status_code}"
        return response.text
    

    
    
    @staticmethod
    def _update_stock_info(stock_code: str, key: str, value: str): 
        print(f"更新股票 {stock_code} 的 {key} 为 {value}")
        return  f"已更新股票 {stock_code} 的 {key} 为 {value}"
    
    def ask(self, msg: str) -> str:
        messages = modelHistoryManager.load_model_messages(self.scene)
        max_history_length = self.scene_config.get("max_history_length", 20) - 1
        if len(messages) > max_history_length:
            messages = messages[-max_history_length:]
        # 如果消息为空或者第一条不是系统，则在第一条添加提示语
        if not messages or messages[0]["role"] != "system":
            messages.insert(0, {"role": "system", "content": self.system_prompt})

        messages.append({"role": "user", "content": msg})
        print(f"发送消息: {msg}")

        
        max_iterations = 5  # 防止无限循环
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                timeout=120
            )
            response_msg = response.choices[0].message

            # 如果没有工具调用，说明拿到了最终答案
            if not response_msg.tool_calls:
                messages.append(response_msg.model_dump())
                break

            # 有工具调用：先保存 assistant 的工具调用消息
            messages.append(response_msg.model_dump())  # 保存包含 tool_calls 的 assistant 消息

            # 逐个执行工具调用
            for tool_call in response_msg.tool_calls:
                tool_name = tool_call.function.name # type: ignore
                tool_args = json.loads(tool_call.function.arguments)  # type: ignore 解析参数字符串
                print(f"工具调用: {tool_name}({tool_args})")

                # 根据工具名称执行对应的真实函数
                tool_result = self._execute_tool(tool_name, tool_args)

                # 追加 tool 角色的返回消息
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })

            # 继续循环，将工具结果交给模型处理

        else:
            # 超过最大迭代次数仍未得到最终答案
            return "工具调用次数过多，请稍后再试"

        modelHistoryManager.save_model_messages(messages, self.scene)
        return response_msg.content if response_msg.content else "该问题暂无法回答"

    def _execute_tool(self, tool_name: str, args: dict) -> str:
        print(f"执行工具函数: {tool_name}，参数: {args}")
        if tool_name == "_get_datetime":
            return get_current_datetime()
        elif tool_name == "query_balance":
            return self.query_balance()
        elif tool_name == "_update_stock_info":
            return self._update_stock_info(args.get("stock_code", ""), args.get("key",""), args.get("value",""))
        elif tool_name == "get_quotes_info":
            return get_quotes_info(args.get("stock_codes", ""))
        else:
            return f"未知工具: {tool_name}"

    
        