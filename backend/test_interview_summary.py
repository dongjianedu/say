#!/usr/bin/env python
"""
测试脚本：使用真实 SRT 文件测试人物专访摘要功能
"""
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.summarizer import SummarizerService
from dotenv import load_dotenv

load_dotenv()


def parse_srt_to_text(srt_path: str) -> str:
    """将 SRT 字幕文件转换为纯文本"""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 移除时间戳和序号
    text = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n', '', content)
    # 移除多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 合并单行
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return ' '.join(lines)


async def main():
    # 配置服务
    service = SummarizerService(
        api_key=os.getenv("SUMMARIZE_API_KEY", ""),
        base_url=os.getenv("SUMMARIZE_BASE_URL", ""),
        model=os.getenv("SUMMARIZE_MODEL", "deepseek-v4-pro")
    )

    print(f"Base URL: {service.base_url}")
    print(f"Model: {service.default_model}")
    print(f"Configured: {service.is_configured}")
    print("=" * 60)

    if not service.is_configured:
        print("错误：服务未配置，请检查 .env 文件")
        return

    # 读取 SRT 文件并转换为文本
    srt_path = "/home/deejac/文档/格调9段资料/audio_sample/潘强龙_2024_07_30.srt"
    if not os.path.exists(srt_path):
        print(f"错误：文件不存在 {srt_path}")
        return

    print(f"正在读取 SRT 文件: {srt_path}")
    interview_text = parse_srt_to_text(srt_path)
    print(f"访谈文本长度: {len(interview_text)} 字符")
    print("=" * 60)

    # 使用 interview_summary 模板
    system_prompt = """你是一个专业的访谈内容分析助手。
请从人物专访中提取以下关键信息：
- 受访者的核心观点
- 重要的人生经历或成就
- 有价值的建议或洞察"""

    user_prompt = f"""请为以下人物专访内容生成摘要（200-500字）：

{interview_text[:5000]}"""  # 限制输入长度避免超出 token 限制

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    print("使用模板: interview_summary")
    print(f"输入文本长度: {len(user_prompt)} 字符")
    print("-" * 60)
    print("正在调用大模型生成摘要...")
    print("-" * 60)

    try:
        summary = await service.chat(
            messages=messages,
            max_tokens=1024,
            temperature=0.3
        )
        
        print("\n" + "=" * 60)
        print("【大模型输出结果】")
        print("=" * 60)
        print(summary)
        print("=" * 60)
        
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())
