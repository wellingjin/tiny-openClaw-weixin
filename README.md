# tiny-openClaw-weixin
迷你版微信小龙虾（openClaw）

# 更多可关注公众号：窥见比特

## 项目简介
这是一个基于微信机器人的轻量级AI助手项目，旨在通过微信与电脑交互，并结合大模型能力（如Qwen）提供智能服务（如天气查询、数学计算等）。项目结构清晰，易于扩展。

## 功能特点
- 微信消息接收与发送
- 支持图片下载与解密
- 对接大模型（如Qwen）进行智能回复
- 轻量级，可以跑任意电脑设备，设置是树莓派等边缘设备
- 内置工具调用能力（天气查询、数学计算、网页抓取等）
- 也可自定义其他能力，比如：
    - 远程控制电脑关机
    - 查询本地文件内容
    - 执行系统命令（需谨慎）
    - 控制智能家居设备
    - 分析视频提取文案



## 项目结构
- `auth/`: 身份认证与账号管理
- `api/`: 微信API封装 
- `messaging/`: 消息收发与处理
- `media/`: 媒体文件（图片等）下载与管理
- `agent/`: AI智能体与工具调用

## 运行环境
- Python 3.8+
- 依赖见 `requirements.txt`
- 安装ollama [ollama](https://github.com/ollama/ollama/releases)
Mac/Linux
```sh
curl -fsSL https://ollama.com/install.sh | OLLAMA_VERSION=0.30.0-rc23 sh
```
Windows
```sh
$env:OLLAMA_VERSION="0.30.0-rc23"; irm https://ollama.com/install.ps1 | iex
```
- 需部署本地大模型（如 Qwen3:0.6b）

## 本地大模型部署
- 使用 Ollama 部署本地大模型（如 Qwen）
- 启动 Ollama 服务：`ollama serve`
- 首次需下载大模型：`ollama pull qwen3:0.6b`

## 快速开始
1. 克隆项目：`git clone https://github.com/wellingjin/tiny-openClaw-weixin.git`
2. 进入项目：`cd tiny-openClaw-weixin`
3. 创建python虚拟环境：`python -m venv .venv`
4. 激活虚拟环境：`source .venv/bin/activate` (Linux/Mac) 或 `.venv\Scripts\activate` (Windows)
5. 安装依赖：`pip install -r requirements.txt`
6. 启动ollama: `ollama serve`
6. 运行 `python cli.py` 首次运行会在终端出现一个二维码，用微信扫码并授权登录即可
7. 如果出现python库依赖错误，pip install 对应的库就好
8. 机器人将自动接收消息并调用AI模型回复

# 扫码关注公众号：窥见比特
![photo](./looking-for-bit.jpg)






