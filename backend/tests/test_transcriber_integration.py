"""
转录服务集成测试 - 使用真实 URL 测试 DashScope 转录功能
"""

import pytest
import os
import sys
import asyncio
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.transcriber import TranscriberService


TEST_AUDIO_URL = "https://gediao9.oss-cn-beijing.aliyuncs.com/panlongqiang_output000.wav"


class TestTranscriberIntegration:
    """转录服务集成测试（使用真实 API）"""

    @pytest.fixture
    def service(self):
        """创建转录服务实例"""
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("TRANSCRIBE_API_KEY", "")
        return TranscriberService(api_key=api_key)

    @pytest.mark.skipif(
        not (os.getenv("DASHSCOPE_API_KEY") or os.getenv("TRANSCRIBE_API_KEY")),
        reason="需要设置 DASHSCOPE_API_KEY 或 TRANSCRIBE_API_KEY 环境变量"
    )
    def test_transcribe_from_real_url(self, service):
        """测试使用真实 URL 进行转录，并打印结果"""
        print("\n" + "=" * 60)
        print(f"开始转录测试，音频 URL: {TEST_AUDIO_URL}")
        print("=" * 60)

        # 运行异步函数
        result = asyncio.run(service.transcribe_from_url(TEST_AUDIO_URL))

        # 打印转录结果
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
        
        # 如果有转录文本，验证非空
        if result["text"]:
            assert len(result["text"]) > 0
            assert len(result["chunks"]) > 0

    @pytest.mark.skipif(
        not (os.getenv("DASHSCOPE_API_KEY") or os.getenv("TRANSCRIBE_API_KEY")),
        reason="需要设置 DASHSCOPE_API_KEY 或 TRANSCRIBE_API_KEY 环境变量"
    )
    def test_transcribe_service_is_configured(self, service):
        """测试服务配置状态"""
        print(f"\n服务配置状态: {'已配置' if service.is_configured else '未配置'}")
        print(f"使用的模型: {service.model}")
        assert service.is_configured, "转录服务未配置，请设置 API Key"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
