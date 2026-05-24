# tiny-openClaw-weixin
迷你版微信小龙虾（openClaw）

# 更多可关注公众号：窥见比特

## 项目简介
这是一个基于微信机器人的轻量级AI助手项目，旨在通过微信与电脑交互，并结合大模型能力（如Qwen）提供智能服务（如天气查询、数学计算等）。项目结构清晰，易于扩展。

## 功能特点
- 微信消息接收与发送
- 支持图片下载与解密
- 对接大模型（如Qwen）进行智能回复

## 快速开始
1. 安装依赖：`pip install -r requirements.txt`
2. 运行 `python cli.py` 并扫码登录
3. 机器人将自动接收消息并调用AI模型回复

## 项目结构
- `auth/`: 身份认证与账号管理
- `api/`: 微信API封装 
- `messaging/`: 消息收发与处理
- `media/`: 媒体文件（图片等）下载与管理
- `agent/`: AI智能体与工具调用

## 运行环境
- Python 3.8+
- 依赖见 `requirements.txt`

## 本地大模型部署
- 使用 Ollama 部署本地大模型（如 Qwen）
- 启动 Ollama 服务：`ollama serve`
- 首次需下载大模型：`ollama run qwen3:0.6b`

# 扫码关注公众号：窥见比特
![photo](./looking-for-bit.jpg)






