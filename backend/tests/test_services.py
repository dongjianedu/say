"""
服务类单元测试
测试 TranscriberService 和 SummarizerService
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from services.transcriber import TranscriberService
from services.summarizer import SummarizerService, PromptTemplate


class TestPromptTemplate:
    """提示词模板测试"""

    def test_load_templates(self):
        """测试加载模板文件"""
        template = PromptTemplate()
        assert template.templates is not None
        assert "summarize" in template.templates
        assert "chat" in template.templates
        assert "templates" in template.templates

    def test_get_interview_summary_template(self):
        """测试获取 interview_summary 模板"""
        template = PromptTemplate()
        result = template.get_template("interview_summary")
        assert "system_prompt" in result
        assert "user_prompt" in result
        assert result["name"] == "人物专访摘要"

    def test_format_prompt(self):
        """测试格式化提示词"""
        template = PromptTemplate()
        prompt = template.format_prompt(
            "summarize",
            text="测试文本",
            min_length=200,
            max_length=500
        )
        assert "测试文本" in prompt["user_prompt"]
        assert "200" in prompt["user_prompt"]
        assert "500" in prompt["user_prompt"]

    def test_template_not_found(self):
        """测试模板不存在"""
        template = PromptTemplate()
        with pytest.raises(KeyError):
            template.get_template("nonexistent_template")


class TestTranscriberService:
    """转录服务测试"""

    def test_init_not_configured(self):
        """测试未配置状态"""
        service = TranscriberService()
        assert service.is_configured is False
        assert service.api_key == ""
        assert service.api_url == ""

    def test_init_configured(self):
        """测试已配置状态"""
        service = TranscriberService(
            api_key="test-key",
            api_url="https://api.example.com/transcribe"
        )
        assert service.is_configured is True
        assert service.api_key == "test-key"
        assert service.api_url == "https://api.example.com/transcribe"

    @pytest.mark.asyncio
    async def test_transcribe_not_configured(self):
        """测试未配置时调用转录"""
        service = TranscriberService()
        with pytest.raises(Exception) as exc_info:
            await service.transcribe(b"audio-data")
        assert "未配置" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transcribe_success(self):
        """测试转录成功"""
        service = TranscriberService(
            api_key="test-key",
            api_url="https://api.example.com/transcribe"
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "text": "测试转录文本",
            "chunks": [{"text": "测试", "timestamp": [0, 1]}],
            "language": "zh"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await service.transcribe(b"audio-data", language="zh")
            
            assert result["text"] == "测试转录文本"
            assert len(result["chunks"]) == 1
            assert result["language"] == "zh"

    @pytest.mark.asyncio
    async def test_transcribe_http_error(self):
        """测试 HTTP 错误"""
        service = TranscriberService(
            api_key="test-key",
            api_url="https://api.example.com/transcribe"
        )
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.HTTPError("API 错误")
            
            with pytest.raises(Exception) as exc_info:
                await service.transcribe(b"audio-data")
            assert "云服务转录失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transcribe_with_language(self):
        """测试带语言参数的转录"""
        service = TranscriberService(
            api_key="test-key",
            api_url="https://api.example.com/transcribe"
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "text": "Test transcription",
            "chunks": [],
            "language": "en"
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await service.transcribe(b"audio-data", language="en")
            
            assert result["language"] == "en"


class TestSummarizerService:
    """摘要服务测试"""

    def test_init_not_configured(self):
        """测试未配置状态"""
        service = SummarizerService()
        assert service.is_configured is False

    def test_init_configured(self):
        """测试已配置状态"""
        service = SummarizerService(
            api_key="test-key",
            base_url="https://api.example.com/v1",
            model="deepseek-v4-pro"
        )
        assert service.is_configured is True
        assert service.api_key == "test-key"
        assert service.base_url == "https://api.example.com/v1"
        assert service.default_model == "deepseek-v4-pro"

    def test_get_chat_url(self):
        """测试聊天接口 URL 生成"""
        service = SummarizerService(
            api_key="test-key",
            base_url="https://api.example.com/v1"
        )
        assert service._get_chat_url() == "https://api.example.com/v1/chat/completions"

    def test_get_chat_url_trailing_slash(self):
        """测试 base_url 带斜杠的情况"""
        service = SummarizerService(
            api_key="test-key",
            base_url="https://api.example.com/v1/"
        )
        assert service._get_chat_url() == "https://api.example.com/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_summarize_not_configured(self):
        """测试未配置时调用摘要"""
        service = SummarizerService()
        with pytest.raises(Exception) as exc_info:
            await service.summarize("测试文本")
        assert "未配置" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_chat_success(self):
        """测试聊天接口成功"""
        service = SummarizerService(
            api_key="test-key",
            base_url="https://api.example.com/v1",
            model="deepseek-v4-pro"
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "我是 DeepSeek 模型"
                    }
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            messages = [{"role": "user", "content": "你是什么模型？"}]
            result = await service.chat(messages)
            
            assert result == "我是 DeepSeek 模型"

    @pytest.mark.asyncio
    async def test_chat_http_error(self):
        """测试聊天接口 HTTP 错误"""
        service = SummarizerService(
            api_key="test-key",
            base_url="https://api.example.com/v1"
        )
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.HTTPError("API 错误")
            
            with pytest.raises(Exception) as exc_info:
                messages = [{"role": "user", "content": "你好"}]
                await service.chat(messages)
            assert "聊天接口调用失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_summarize_success(self):
        """测试摘要成功"""
        service = SummarizerService(
            api_key="test-key",
            base_url="https://api.example.com/v1",
            model="deepseek-v4-pro"
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "这是一段摘要文本"
                    }
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await service.summarize("这是一段需要摘要的长文本")
            
            assert result["summary"] == "这是一段摘要文本"
            assert result["model"] == "deepseek-v4-pro"

    @pytest.mark.asyncio
    async def test_summarize_custom_model(self):
        """测试自定义模型"""
        service = SummarizerService(
            api_key="test-key",
            base_url="https://api.example.com/v1",
            model="deepseek-v4-pro"
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "GPT-4 摘要"
                    }
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await service.summarize("测试文本", model="gpt-4")
            
            assert result["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_summarize_with_length_params(self):
        """测试长度参数"""
        service = SummarizerService(
            api_key="test-key",
            base_url="https://api.example.com/v1",
            model="deepseek-v4-pro"
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "短摘要"
                    }
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await service.summarize(
                "测试文本",
                max_length=100,
                min_length=20
            )
            
            assert result["summary"] == "短摘要"

    @pytest.mark.asyncio
    async def test_summarize_http_error(self):
        """测试 HTTP 错误"""
        service = SummarizerService(
            api_key="test-key",
            base_url="https://api.example.com/v1"
        )
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.HTTPError("API 错误")
            
            with pytest.raises(Exception) as exc_info:
                await service.summarize("测试文本")
            assert "调用失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_summarize_empty_response(self):
        """测试空响应"""
        service = SummarizerService(
            api_key="test-key",
            base_url="https://api.example.com/v1"
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": ""
                    }
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await service.summarize("测试文本")
            
            assert result["summary"] == ""
