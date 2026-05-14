"""
转录服务单元测试 - 使用本地测试音频文件
"""

import pytest
import os
import sys
import asyncio
import json
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.transcriber import TranscriberService


TEST_AUDIO_PATH = "/home/deejac/dev_tools/github/alibabacloud-bailian-speech-demo/samples/sample-data/hello_world_male_16k_16bit_mono.wav"


class TestTranscriberUnit:
    """转录服务单元测试"""

    @pytest.fixture
    def service(self):
        """创建转录服务实例"""
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("TRANSCRIBE_API_KEY", "")
        return TranscriberService(api_key=api_key)

    @pytest.fixture
    def test_audio_bytes(self):
        """加载测试音频文件"""
        assert os.path.exists(TEST_AUDIO_PATH), f"测试音频文件不存在: {TEST_AUDIO_PATH}"
        with open(TEST_AUDIO_PATH, "rb") as f:
            return f.read()

    @pytest.fixture
    def test_webm_bytes(self):
        """从 WAV 生成 WebM/Opus 测试文件"""
        webm_path = "/tmp/test_webm_opus.webm"
        if not os.path.exists(webm_path):
            result = subprocess.run([
                "ffmpeg", "-y", "-i", TEST_AUDIO_PATH,
                "-c:a", "libopus", "-b:a", "64k",
                webm_path
            ], capture_output=True, text=True)
            assert result.returncode == 0, f"ffmpeg failed: {result.stderr}"
        with open(webm_path, "rb") as f:
            return f.read()

    @pytest.mark.skipif(
        not (os.getenv("DASHSCOPE_API_KEY") or os.getenv("TRANSCRIBE_API_KEY")),
        reason="需要设置 DASHSCOPE_API_KEY 或 TRANSCRIBE_API_KEY 环境变量"
    )
    def test_transcribe_audio_file(self, service, test_audio_bytes):
        """测试转录本地音频文件并打印结果"""
        print("\n" + "=" * 60)
        print("转录服务单元测试")
        print("=" * 60)
        print(f"\n测试文件: {TEST_AUDIO_PATH}")
        print(f"文件大小: {len(test_audio_bytes)} 字节")
        print(f"使用模型: {service.model}")

        # 运行异步转录
        result = asyncio.run(service.transcribe(test_audio_bytes))

        # 打印结果
        print("\n" + "=" * 60)
        print("转录结果:")
        print("=" * 60)
        print(f"\n检测到的语言: {result['language']}")
        print(f"\n完整转录文本:\n{result['text']}")
        print(f"\n分块数量: {len(result['chunks'])}")

        print("\n分块详情:")
        for i, chunk in enumerate(result['chunks'], 1):
            print(f"  [{i}] {chunk['text']}")
            print(f"      时间: {chunk.get('start_time', 0)}ms - {chunk.get('end_time', 0)}ms")

        print("\n" + "=" * 60)
        print("完整 JSON 结果:")
        print("=" * 60)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("=" * 60 + "\n")

        # 基本断言
        assert "text" in result
        assert "chunks" in result
        assert "language" in result
        assert isinstance(result["text"], str)
        assert isinstance(result["chunks"], list)

        # hello_world_male_16k_16bit_mono.wav 应该包含 "Hello world" 或类似内容
        if result["text"]:
            assert len(result["text"]) > 0
            assert len(result["chunks"]) > 0

    @pytest.mark.skipif(
        not (os.getenv("DASHSCOPE_API_KEY") or os.getenv("TRANSCRIBE_API_KEY")),
        reason="需要设置 DASHSCOPE_API_KEY 或 TRANSCRIBE_API_KEY 环境变量"
    )
    def test_transcribe_webm_file(self, service, test_webm_bytes):
        """测试转录 WebM/Opus 格式文件"""
        print("\n" + "=" * 60)
        print("WebM/Opus 格式转录测试")
        print("=" * 60)
        print(f"文件大小: {len(test_webm_bytes)} 字节")
        print(f"使用模型: {service.model}")

        assert service._detect_format(test_webm_bytes) == "webm"

        result = asyncio.run(service.transcribe(test_webm_bytes))

        print("\n" + "=" * 60)
        print("转录结果:")
        print("=" * 60)
        print(f"\n检测到的语言: {result['language']}")
        print(f"\n完整转录文本:\n{result['text']}")
        print(f"\n分块数量: {len(result['chunks'])}")

        print("\n分块详情:")
        for i, chunk in enumerate(result['chunks'], 1):
            print(f"  [{i}] {chunk['text']}")
            print(f"      时间: {chunk.get('start_time', 0)}ms - {chunk.get('end_time', 0)}ms")

        print("=" * 60 + "\n")

        assert "text" in result
        assert "chunks" in result
        assert isinstance(result["text"], str)
        assert isinstance(result["chunks"], list)
        assert len(result["text"]) > 0

    @pytest.mark.skipif(
        not (os.getenv("DASHSCOPE_API_KEY") or os.getenv("TRANSCRIBE_API_KEY")),
        reason="需要设置 DASHSCOPE_API_KEY 或 TRANSCRIBE_API_KEY 环境变量"
    )
    def test_transcribe_service_configured(self, service):
        """测试服务配置状态"""
        print(f"\n服务配置状态: {'已配置' if service.is_configured else '未配置'}")
        print(f"使用的模型: {service.model}")
        assert service.is_configured, "转录服务未配置"

    def test_detect_format_wav(self, service):
        """测试 WAV 格式检测"""
        wav_header = b'RIFF' + b'\x00' * 100
        assert service._detect_format(wav_header) == "wav"

    def test_detect_format_mp3(self, service):
        """测试 MP3 格式检测"""
        mp3_header = b'\xff\xfb' + b'\x00' * 100
        assert service._detect_format(mp3_header) == "mp3"

    def test_detect_format_webm(self, service):
        """测试 WebM 格式检测"""
        webm_header = b'\x1a\x45\xdf\xa3' + b'\x00' * 100
        assert service._detect_format(webm_header) == "webm"

    def test_detect_format_opus(self, service):
        """测试 Opus 格式检测"""
        opus_header = b'OpusHead' + b'\x00' * 100
        assert service._detect_format(opus_header) == "opus"

    def test_detect_default_sample_rate(self, service):
        """测试默认采样率"""
        assert service._detect_sample_rate(b"invalid_data", "wav") == 16000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
