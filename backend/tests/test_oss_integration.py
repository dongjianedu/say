"""
OSS 上传服务集成测试
"""

import pytest
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.oss import OSSService


TEST_FILE_PATH = "/home/deejac/文档/格调9问资料/audio_sample/潘强龙_2024_07_30.srt"


class TestOSSIntegration:
    """OSS 上传集成测试"""

    @pytest.fixture
    def service(self):
        """创建 OSS 服务实例"""
        return OSSService(
            access_key_id=os.getenv("OSS_ACCESS_KEY_ID", ""),
            access_key_secret=os.getenv("OSS_ACCESS_KEY_SECRET", ""),
            endpoint=os.getenv("OSS_ENDPOINT", ""),
            bucket_name=os.getenv("OSS_BUCKET_NAME", "gediao9"),
            accesspoint_url=os.getenv("OSS_ACCESSPOINT_URL", "")
        )

    @pytest.mark.skipif(
        not (os.getenv("OSS_ACCESS_KEY_ID") and os.getenv("OSS_ACCESS_KEY_SECRET")),
        reason="需要设置 OSS_ACCESS_KEY_ID 和 OSS_ACCESS_KEY_SECRET 环境变量"
    )
    def test_upload_file_to_oss(self, service):
        """测试上传文件到 OSS 并打印结果"""
        print("\n" + "=" * 60)
        print("OSS 上传测试")
        print("=" * 60)
        print(f"\n接入点: {service.endpoint}")
        print(f"Bucket: {service.bucket_name}")
        print(f"测试文件: {TEST_FILE_PATH}")

        assert os.path.exists(TEST_FILE_PATH), f"测试文件不存在: {TEST_FILE_PATH}"

        with open(TEST_FILE_PATH, "rb") as f:
            file_bytes = f.read()

        print(f"文件大小: {len(file_bytes)} 字节")

        # 上传文件
        result = asyncio.run(service.upload_file(
            file_bytes=file_bytes,
            filename="潘强龙_2024_07_30.srt",
            folder="test"
        ))

        # 打印结果
        print("\n" + "=" * 60)
        print("上传结果:")
        print("=" * 60)
        print(f"\n文件 URL: {result}")
        print("=" * 60 + "\n")

        # 验证 URL 格式
        assert result.startswith("https://")
        assert ".srt" in result
        assert "test/" in result

    @pytest.mark.skipif(
        not (os.getenv("OSS_ACCESS_KEY_ID") and os.getenv("OSS_ACCESS_KEY_SECRET")),
        reason="需要设置 OSS_ACCESS_KEY_ID 和 OSS_ACCESS_KEY_SECRET 环境变量"
    )
    def test_oss_service_configured(self, service):
        """测试 OSS 服务配置状态"""
        print(f"\nOSS 服务配置状态: {'已配置' if service.is_configured else '未配置'}")
        print(f"接入点: {service.endpoint}")
        print(f"Bucket: {service.bucket_name}")
        assert service.is_configured, "OSS 服务未配置"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
