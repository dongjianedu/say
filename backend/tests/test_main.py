"""
后端 API 接口单元测试
测试健康检查、转录、摘要三个接口
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, transcriber_service, summarizer_service


class TestHealthCheck:
    """健康检查接口测试"""

    def test_health_check_returns_ok(self, client):
        """测试健康检查返回正常状态"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "transcribe_service" in data
        assert "summarize_service" in data

    def test_health_check_service_status(self, client):
        """测试服务配置状态显示"""
        response = client.get("/health")
        data = response.json()
        assert data["transcribe_service"] in ["configured", "not configured"]
        assert data["summarize_service"] in ["configured", "not configured"]


class TestTranscribeEndpoint:
    """转录接口测试"""

    def test_transcribe_success(self, client, mock_audio_bytes, mock_transcribe_result):
        """测试转录成功"""
        with patch.object(
            transcriber_service,
            'transcribe',
            new_callable=AsyncMock,
            return_value=mock_transcribe_result
        ):
            audio_file = io.BytesIO(mock_audio_bytes)
            response = client.post(
                "/transcribe",
                files={"audio": ("test.wav", audio_file, "audio/wav")}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["text"] == "这是一段测试转录文本"
            assert len(data["chunks"]) == 2
            assert data["language"] == "zh"

    def test_transcribe_with_language(self, client, mock_audio_bytes):
        """测试指定语言参数转录"""
        mock_result = {
            "text": "This is a test transcription",
            "chunks": [],
            "language": "en"
        }
        with patch.object(
            transcriber_service,
            'transcribe',
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            audio_file = io.BytesIO(mock_audio_bytes)
            response = client.post(
                "/transcribe",
                files={"audio": ("test.wav", audio_file, "audio/wav")},
                params={"language": "en"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["language"] == "en"
            transcriber_service.transcribe.assert_called_once()

    def test_transcribe_empty_audio(self, client):
        """测试空音频文件"""
        mock_result = {
            "text": "",
            "chunks": [],
            "language": "auto"
        }
        with patch.object(
            transcriber_service,
            'transcribe',
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            audio_file = io.BytesIO(b"")
            response = client.post(
                "/transcribe",
                files={"audio": ("empty.wav", audio_file, "audio/wav")}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["text"] == ""

    def test_transcribe_service_error(self, client, mock_audio_bytes):
        """测试转录服务错误"""
        with patch.object(
            transcriber_service,
            'transcribe',
            new_callable=AsyncMock,
            side_effect=Exception("云服务转录失败: API 错误")
        ):
            audio_file = io.BytesIO(mock_audio_bytes)
            response = client.post(
                "/transcribe",
                files={"audio": ("test.wav", audio_file, "audio/wav")}
            )
            
            assert response.status_code == 500
            data = response.json()
            assert "转录失败" in data["detail"]

    def test_transcribe_response_format(self, client, mock_audio_bytes):
        """测试转录响应格式"""
        mock_result = {
            "text": "测试文本",
            "chunks": [{"text": "测试", "timestamp": [0, 1]}],
            "language": "zh"
        }
        with patch.object(
            transcriber_service,
            'transcribe',
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            audio_file = io.BytesIO(mock_audio_bytes)
            response = client.post(
                "/transcribe",
                files={"audio": ("test.wav", audio_file, "audio/wav")}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "text" in data
            assert "chunks" in data
            assert "language" in data
            assert isinstance(data["chunks"], list)
            assert isinstance(data["language"], str)


class TestSummarizeEndpoint:
    """摘要接口测试"""

    def test_summarize_success(self, client, mock_summarize_result):
        """测试摘要生成成功"""
        mock_result = {
            "summary": "这是一段摘要文本",
            "model": "deepseek-v4-pro",
            "template": "summarize"
        }
        with patch.object(
            summarizer_service,
            'summarize_with_template',
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            response = client.post(
                "/summarize",
                json={"text": "这是一段需要摘要的长文本内容..."}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["summary"] == "这是一段摘要文本"
            assert data["model"] == "deepseek-v4-pro"
            assert data["template"] == "summarize"

    def test_summarize_with_custom_model(self, client):
        """测试使用自定义模型"""
        mock_result = {
            "summary": "自定义模型摘要",
            "model": "gpt-4",
            "template": "summarize"
        }
        with patch.object(
            summarizer_service,
            'summarize_with_template',
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            response = client.post(
                "/summarize",
                json={
                    "text": "测试文本",
                    "model": "gpt-4"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["model"] == "gpt-4"

    def test_summarize_with_template(self, client):
        """测试使用指定模板"""
        mock_result = {
            "summary": "人物专访摘要",
            "model": "deepseek-v4-pro",
            "template": "interview_summary"
        }
        with patch.object(
            summarizer_service,
            'summarize_with_template',
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            response = client.post(
                "/summarize",
                json={
                    "text": "测试文本",
                    "template_name": "interview_summary"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["template"] == "interview_summary"
            summarizer_service.summarize_with_template.assert_called_once()
            call_kwargs = summarizer_service.summarize_with_template.call_args[1]
            assert call_kwargs["template_name"] == "interview_summary"

    def test_summarize_empty_text(self, client):
        """测试空文本摘要"""
        mock_result = {
            "summary": "",
            "model": "deepseek-v4-pro",
            "template": "summarize"
        }
        with patch.object(
            summarizer_service,
            'summarize_with_template',
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            response = client.post(
                "/summarize",
                json={"text": ""}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["summary"] == ""

    def test_summarize_service_error(self, client):
        """测试摘要服务错误"""
        with patch.object(
            summarizer_service,
            'summarize_with_template',
            new_callable=AsyncMock,
            side_effect=Exception("云服务摘要失败: API 错误")
        ):
            response = client.post(
                "/summarize",
                json={"text": "测试文本"}
            )
            
            assert response.status_code == 500
            data = response.json()
            assert "摘要生成失败" in data["detail"]

    def test_summarize_response_format(self, client):
        """测试摘要响应格式"""
        mock_result = {
            "summary": "测试摘要",
            "model": "deepseek-v4-pro",
            "template": "summarize"
        }
        with patch.object(
            summarizer_service,
            'summarize_with_template',
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            response = client.post(
                "/summarize",
                json={"text": "测试文本"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "summary" in data
            assert "model" in data
            assert "template" in data
            assert isinstance(data["summary"], str)
            assert isinstance(data["model"], str)
            assert isinstance(data["template"], str)

    def test_summarize_missing_text(self, client):
        """测试缺少文本参数"""
        response = client.post(
            "/summarize",
            json={}
        )
        
        assert response.status_code == 422
