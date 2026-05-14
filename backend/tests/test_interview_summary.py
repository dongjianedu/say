"""
人物专访摘要集成测试
使用真实 SRT 文件测试 interview_summary 模板
"""

import pytest
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.summarizer import SummarizerService, PromptTemplate
from dotenv import load_dotenv

load_dotenv()


def parse_srt_to_text(srt_path: str) -> str:
    """将 SRT 字幕文件转换为纯文本"""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    text = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n', '', content)
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return ' '.join(lines)


@pytest.fixture
def service():
    """创建配置好的 SummarizerService 实例"""
    return SummarizerService(
        api_key=os.getenv("SUMMARIZE_API_KEY", ""),
        base_url=os.getenv("SUMMARIZE_BASE_URL", ""),
        model=os.getenv("SUMMARIZE_MODEL", "deepseek-v4-pro")
    )


@pytest.fixture
def prompt_template():
    """创建提示词模板管理器"""
    return PromptTemplate()


@pytest.fixture
def interview_text():
    """读取并解析 SRT 访谈文件"""
    srt_path = "/home/deejac/文档/格调9问资料/audio_sample/潘强龙_2024_07_30.srt"
    if not os.path.exists(srt_path):
        pytest.skip(f"测试文件不存在: {srt_path}")
    return parse_srt_to_text(srt_path)


def test_prompt_template_loads_interview_summary(prompt_template):
    """测试提示词模板能正确加载 interview_summary 模板"""
    template = prompt_template.get_template("interview_summary")
    
    assert "system_prompt" in template
    assert "user_prompt" in template
    assert "name" in template
    assert template["name"] == "人物专访摘要"
    assert "访谈" in template["system_prompt"] or "专访" in template["system_prompt"]


def test_prompt_template_format(prompt_template):
    """测试提示词模板格式化"""
    prompt = prompt_template.format_prompt(
        "interview_summary",
        text="测试文本",
        min_length=200,
        max_length=500
    )
    
    assert "system_prompt" in prompt
    assert "user_prompt" in prompt
    assert "测试文本" in prompt["user_prompt"]


@pytest.mark.asyncio
async def test_interview_summary_from_template(service, prompt_template, interview_text, capsys):
    """
    测试使用 templates.yaml 中的 interview_summary 模板生成人物专访摘要
    验证：
    1. 模板正确加载
    2. 能够成功调用 API
    3. 返回的摘要非空且包含关键信息
    """
    assert service.is_configured, "服务未配置"
    
    # 从模板获取提示词
    prompt = prompt_template.format_prompt(
        "interview_summary",
        text=interview_text[:5000],
        min_length=200,
        max_length=500
    )
    
    print(f"\n使用的模板: {prompt['name']}")
    print(f"System Prompt: {prompt['system_prompt'][:100]}...")
    print(f"User Prompt 长度: {len(prompt['user_prompt'])} 字符")

    messages = [
        {"role": "system", "content": prompt["system_prompt"]},
        {"role": "user", "content": prompt["user_prompt"]}
    ]

    summary = await service.chat(
        messages=messages,
        max_tokens=1024,
        temperature=0.3
    )

    print("\n" + "=" * 60)
    print("【人物专访摘要结果】")
    print("=" * 60)
    print(summary)
    print("=" * 60)

    assert summary, "摘要不应为空"
    assert len(summary) > 50, "摘要长度应大于50字符"
    assert any(keyword in summary for keyword in ["潘", "企业家", "中科", "浙江"]), \
        "摘要应包含访谈中的关键信息"


@pytest.mark.asyncio
async def test_summarize_with_template_method(service, interview_text, capsys):
    """
    测试使用 summarize_with_template 方法（直接使用模板）
    """
    truncated_text = interview_text[:5000]
    
    result = await service.summarize_with_template(
        text=truncated_text,
        template_name="interview_summary",
        max_tokens=1024,
        temperature=0.3,
        min_length=200,
        max_length=500
    )

    print("\n" + "=" * 60)
    print("【使用 summarize_with_template 方法的结果】")
    print("=" * 60)
    print(f"模板: {result['template']}")
    print(f"模型: {result['model']}")
    print("-" * 60)
    print(result['summary'])
    print("=" * 60)

    assert result['summary'], "摘要不应为空"
    assert result['template'] == "interview_summary"
    assert len(result['summary']) > 50


@pytest.mark.asyncio
async def test_summarize_with_default_template(service, interview_text, capsys):
    """
    测试使用默认的 summarize 方法（使用 summarize 模板）
    """
    truncated_text = interview_text[:3000]
    
    result = await service.summarize(
        text=truncated_text,
        template_name="summarize",
        max_length=300,
        min_length=100
    )

    print("\n" + "=" * 60)
    print("【使用默认 summarize 模板的结果】")
    print("=" * 60)
    print(result['summary'])
    print("=" * 60)

    assert result['summary'], "摘要不应为空"
    assert len(result['summary']) > 30
