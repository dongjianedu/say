"""
文本摘要服务 - 调用云服务 API
支持的服务商：
- OpenAI GPT API
- 阿里云 DashScope (OpenAI 兼容接口)
- 其他兼容 OpenAI 接口的 LLM 服务
"""

import httpx
import logging
import os
import yaml
from typing import Optional

logger = logging.getLogger(__name__)

class PromptTemplate:
    """提示词模板管理器"""
    
    def __init__(self, template_path: str = None):
        if template_path is None:
            template_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "prompts",
                "templates.yaml"
            )
        self.template_path = template_path
        self.templates = self._load_templates()
    
    def _load_templates(self) -> dict:
        """加载模板文件"""
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to load prompt templates: {e}")
            return {}
    
    def get_template(self, name: str) -> dict:
        """获取指定名称的模板"""
        # 先从顶层查找
        if name in self.templates:
            return self.templates[name]
        # 再从 templates 子节点查找
        if "templates" in self.templates and name in self.templates["templates"]:
            return self.templates["templates"][name]
        raise KeyError(f"Prompt template '{name}' not found")
    
    def format_prompt(self, name: str, **kwargs) -> dict:
        """获取并格式化模板"""
        template = self.get_template(name)
        system_prompt = template.get("system_prompt", "").format(**kwargs)
        user_prompt = template.get("user_prompt", "").format(**kwargs)
        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "name": template.get("name", name)
        }


class SummarizerService:
    def __init__(self, api_key: str = "", base_url: str = "", model: str = "", template_path: str = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = model or "gpt-3.5-turbo"
        self.is_configured = bool(api_key and base_url)
        self.prompt_template = PromptTemplate(template_path)

    def _get_chat_url(self) -> str:
        """获取 Chat Completions 接口地址"""
        return f"{self.base_url}/chat/completions"

    async def chat(
        self,
        messages: list,
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """
        通用聊天接口
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            model: 模型名称
            max_tokens: 最大 token 数
            temperature: 温度参数
            
        Returns:
            模型回复文本
        """
        if not self.is_configured:
            raise Exception("摘要服务未配置，请设置 SUMMARIZE_API_KEY 和 SUMMARIZE_BASE_URL")

        actual_model = model if model and model != "default" else self.default_model

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                payload = {
                    "model": actual_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }

                response = await client.post(
                    self._get_chat_url(),
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return content.strip()

        except httpx.HTTPError as e:
            logger.error(f"Chat API error: {e}")
            raise Exception(f"聊天接口调用失败: {str(e)}")
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise

    async def summarize(
        self,
        text: str,
        model: Optional[str] = None,
        max_length: int = 150,
        min_length: int = 40,
        template_name: str = "summarize"
    ) -> dict:
        """
        调用云服务生成文本摘要

        Args:
            text: 输入文本
            model: 模型名称
            max_length: 最大长度
            min_length: 最小长度
            template_name: 提示词模板名称

        Returns:
            {"summary": "摘要文本", "model": "模型名称"}
        """
        if not self.is_configured:
            raise Exception("摘要服务未配置，请设置 SUMMARIZE_API_KEY 和 SUMMARIZE_BASE_URL")

        try:
            prompt = self.prompt_template.format_prompt(
                template_name,
                text=text,
                min_length=min_length,
                max_length=max_length
            )

            messages = [
                {"role": "system", "content": prompt["system_prompt"]},
                {"role": "user", "content": prompt["user_prompt"]}
            ]

            content = await self.chat(
                messages=messages,
                model=model,
                max_tokens=max_length,
                temperature=0.3,
            )

            return {
                "summary": content,
                "model": model or self.default_model
            }

        except httpx.HTTPError as e:
            logger.error(f"Summarization API error: {e}")
            raise Exception(f"云服务摘要失败: {str(e)}")
        except Exception as e:
            logger.error(f"Summarization error: {e}")
            raise

    async def summarize_with_template(
        self,
        text: str,
        template_name: str = "interview_summary",
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        **kwargs
    ) -> dict:
        """
        使用指定模板生成摘要

        Args:
            text: 输入文本
            template_name: 模板名称
            model: 模型名称
            max_tokens: 最大 token 数
            temperature: 温度参数
            **kwargs: 其他模板变量

        Returns:
            {"summary": "摘要文本", "model": "模型名称", "template": "模板名称"}
        """
        if not self.is_configured:
            raise Exception("摘要服务未配置")

        try:
            format_kwargs = {
                "text": text,
                "min_length": kwargs.get("min_length", 200),
                "max_length": kwargs.get("max_length", 500),
            }
            format_kwargs.update(kwargs)

            prompt = self.prompt_template.format_prompt(
                template_name,
                **format_kwargs
            )

            messages = [
                {"role": "system", "content": prompt["system_prompt"]},
                {"role": "user", "content": prompt["user_prompt"]}
            ]

            content = await self.chat(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            return {
                "summary": content,
                "model": model if model and model != "default" else self.default_model,
                "template": template_name
            }

        except Exception as e:
            logger.error(f"Template summarization error: {e}")
            raise
