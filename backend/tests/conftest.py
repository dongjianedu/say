import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, transcriber_service, summarizer_service

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_audio_bytes():
    return b"fake-audio-data-wav-format"

@pytest.fixture
def mock_transcribe_result():
    return {
        "text": "这是一段测试转录文本",
        "chunks": [
            {"text": "这是一段", "timestamp": [0, 2]},
            {"text": "测试转录文本", "timestamp": [2, 4]}
        ],
        "language": "zh"
    }

@pytest.fixture
def mock_summarize_result():
    return {
        "summary": "这是一段摘要文本",
        "model": "deepseek-v4-pro"
    }
