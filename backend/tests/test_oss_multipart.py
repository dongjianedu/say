"""
OSS 分片上传集成测试
"""

import pytest
import os
import sys
import asyncio
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.oss import OSSService, DEFAULT_PART_SIZE


class TestOSSMultipartUpload:
    """OSS 分片上传集成测试"""

    @pytest.fixture
    def service(self):
        """创建 OSS 服务实例"""
        return OSSService(
            access_key_id=os.getenv("OSS_ACCESS_KEY_ID", ""),
            access_key_secret=os.getenv("OSS_ACCESS_KEY_SECRET", ""),
            endpoint=os.getenv("OSS_ENDPOINT", ""),
            bucket_name=os.getenv("OSS_BUCKET_NAME", "gediao9"),
            accesspoint_url=os.getenv("OSS_ACCESSPOINT_URL", ""),
            region="cn-beijing"
        )

    @pytest.mark.skipif(
        not (os.getenv("OSS_ACCESS_KEY_ID") and os.getenv("OSS_ACCESS_KEY_SECRET")),
        reason="需要设置 OSS_ACCESS_KEY_ID 和 OSS_ACCESS_KEY_SECRET 环境变量"
    )
    def test_multipart_upload_small_threshold(self, service):
        """测试分片上传（使用小阈值触发分片）"""
        print("\n" + "=" * 60)
        print("分片上传测试")
        print("=" * 60)

        # 生成 1MB 测试数据（使用小阈值触发分片）
        test_data = os.urandom(1024 * 1024)
        test_part_size = 256 * 1024  # 256KB 分片
        test_threshold = 512 * 1024  # 512KB 阈值

        print(f"测试数据大小: {len(test_data)} 字节")
        print(f"分片大小: {test_part_size} 字节")
        print(f"触发阈值: {test_threshold} 字节")
        print(f"预期分片数: {len(test_data) // test_part_size + 1}")

        result = asyncio.run(service.upload_file(
            file_bytes=test_data,
            filename="test_multipart.bin",
            folder="test",
            multipart_threshold=test_threshold,
            part_size=test_part_size
        ))

        print(f"\n上传成功!")
        print(f"文件 URL: {result}")
        print("=" * 60)

        assert result.startswith("https://")
        assert "test_multipart.bin" not in result
        assert "test/" in result

    @pytest.mark.skipif(
        not (os.getenv("OSS_ACCESS_KEY_ID") and os.getenv("OSS_ACCESS_KEY_SECRET")),
        reason="需要设置 OSS_ACCESS_KEY_ID 和 OSS_ACCESS_KEY_SECRET 环境变量"
    )
    def test_simple_upload_small_file(self, service):
        """测试简单上传（小文件不触发分片）"""
        print("\n" + "=" * 60)
        print("简单上传测试（不触发分片）")
        print("=" * 60)

        test_data = b"Hello, this is a small test file."
        test_threshold = 10 * 1024 * 1024  # 10MB 阈值

        print(f"测试数据大小: {len(test_data)} 字节")
        print(f"触发阈值: {test_threshold} 字节")
        print("预期: 使用简单上传")

        result = asyncio.run(service.upload_file(
            file_bytes=test_data,
            filename="test_simple.txt",
            folder="test",
            multipart_threshold=test_threshold
        ))

        print(f"\n上传成功!")
        print(f"文件 URL: {result}")
        print("=" * 60)

        assert result.startswith("https://")
        assert "test/" in result

    @pytest.mark.skipif(
        not (os.getenv("OSS_ACCESS_KEY_ID") and os.getenv("OSS_ACCESS_KEY_SECRET")),
        reason="需要设置 OSS_ACCESS_KEY_ID 和 OSS_ACCESS_KEY_SECRET 环境变量"
    )
    def test_oss_service_configured(self, service):
        """测试 OSS 服务配置状态"""
        print(f"\nOSS 服务配置状态: {'已配置' if service.is_configured else '未配置'}")
        print(f"Endpoint: {service.endpoint}")
        print(f"Bucket: {service.bucket_name}")
        print(f"Region: {service.region}")
        assert service.is_configured, "OSS 服务未配置"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
