"""
阿里云 OSS 上传服务
用于将文件上传到阿里云对象存储
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Optional

import oss2

logger = logging.getLogger(__name__)


class OSSService:
    def __init__(
        self,
        access_key_id: str = "",
        access_key_secret: str = "",
        endpoint: str = "",
        bucket_name: str = "",
        accesspoint_url: str = ""
    ):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        self.accesspoint_url = accesspoint_url
        self.is_configured = bool(access_key_id and access_key_secret and endpoint and bucket_name)
        
        if self.is_configured:
            auth = oss2.Auth(access_key_id, access_key_secret)
            self.bucket = oss2.Bucket(auth, endpoint, bucket_name)
        else:
            self.bucket = None

    async def upload_file(
        self,
        file_bytes: bytes,
        filename: str,
        folder: str = "audio",
        content_type: Optional[str] = None
    ) -> str:
        """
        上传文件到 OSS

        Args:
            file_bytes: 文件字节数据
            filename: 原始文件名
            folder: OSS 中的文件夹路径
            content_type: 文件 MIME 类型

        Returns:
            文件的访问 URL
        """
        if not self.is_configured:
            raise Exception("OSS 服务未配置，请设置 OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_ENDPOINT, OSS_BUCKET_NAME")

        # 生成唯一文件名
        ext = os.path.splitext(filename)[1]
        unique_filename = f"{folder}/{datetime.now().strftime('%Y%m%d')}/{uuid.uuid4().hex}{ext}"

        try:
            headers = {}
            if content_type:
                headers["Content-Type"] = content_type

            self.bucket.put_object(unique_filename, file_bytes, headers=headers)

            # 构建访问 URL（优先使用接入点 URL）

            base_url = f"https://{self.bucket_name}.{self.endpoint}"
            
            file_url = f"{base_url}/{unique_filename}"
            logger.info(f"文件上传成功: {file_url}")
            return file_url

        except oss2.exceptions.OssError as e:
            logger.error(f"OSS 上传失败: {e}")
            raise Exception(f"OSS 上传失败: {str(e)}")
        except Exception as e:
            logger.error(f"文件上传错误: {e}")
            raise Exception(f"文件上传错误: {str(e)}")
