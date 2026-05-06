"""
文本摘要服务 - 调用云服务 API
支持的服务商：
- OpenAI GPT API
- 阿里云通义千问
- 百度文心一言
- 其他自定义 LLM 服务
"""

import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SummarizerService:
    def __init__(self, api_key: str = "", api_url: str = ""):
        self.api_key = api_key
        self.api_url = api_url
        self.is_configured = bool(api_key and api_url)

    async def summarize(
        self, 
        text: str, 
        model: Optional[str] = None,
        max_length: int = 150,
        min_length: int = 40
    ) -> dict:
        """
        调用云服务生成文本摘要
        
        Args:
            text: 输入文本
            model: 模型名称
            max_length: 最大长度
            min_length: 最小长度
            
        Returns:
            {"summary": "摘要文本", "model": "模型名称"}
        """
        if not self.is_configured:
            raise Exception("摘要服务未配置，请设置 SUMMARIZE_API_KEY 和 SUMMARIZE_API_URL")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # 示例：调用 OpenAI Chat Completions API
                # 实际使用时根据具体云服务调整
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                
                payload = {
                    "model": model or "gpt-3.5-turbo",
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是一个专业的文本摘要助手。请将用户输入的文本精简为摘要，保持关键信息完整。"
                        },
                        {
                            "role": "user",
                            "content": f"请为以下内容生成摘要（{min_length}-{max_length}字）：\n\n{text}"
                        }
                    ],
                    "max_tokens": max_length,
                    "temperature": 0.3,
                }

                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

                # 解析 OpenAI 响应格式
                summary = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                return {
                    "summary": summary.strip(),
                    "model": model or "gpt-3.5-turbo"
                }

        except httpx.HTTPError as e:
            logger.error(f"Cloud summarization API error: {e}")
            raise Exception(f"云服务摘要失败: {str(e)}")
        except Exception as e:
            logger.error(f"Summarization error: {e}")
            raise
