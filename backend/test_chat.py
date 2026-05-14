#!/usr/bin/env python
"""
测试脚本：询问大模型"你是什么模型"
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.summarizer import SummarizerService
from dotenv import load_dotenv

load_dotenv()

async def main():
    service = SummarizerService(
        api_key=os.getenv("SUMMARIZE_API_KEY", ""),
        base_url=os.getenv("SUMMARIZE_BASE_URL", ""),
        model=os.getenv("SUMMARIZE_MODEL", "deepseek-v4-pro")
    )

    print(f"Base URL: {service.base_url}")
    print(f"Model: {service.default_model}")
    print(f"Configured: {service.is_configured}")
    print("-" * 50)

    if not service.is_configured:
        print("错误：服务未配置，请检查 .env 文件")
        return

    messages = [
        {"role": "user", "content": "你是什么模型？"}
    ]

    print("提问: 你是什么模型？")
    print("-" * 50)

    try:
        response = await service.chat(messages)
        print(f"回答: {response}")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    asyncio.run(main())
