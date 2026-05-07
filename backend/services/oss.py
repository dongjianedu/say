"""
阿里云 OSS 上传服务
支持简单上传和分片上传
"""

import os
import io
import uuid
import logging
from datetime import datetime
from typing import Optional

import oss2
import alibabacloud_oss_v2 as oss_v2

logger = logging.getLogger(__name__)

DEFAULT_PART_SIZE = 10 * 1024 * 1024  # 10MB
DEFAULT_MULTIPART_THRESHOLD = 100 * 1024 * 1024  # 100MB


class OSSService:
    def __init__(
        self,
        access_key_id: str = "",
        access_key_secret: str = "",
        endpoint: str = "",
        bucket_name: str = "",
        accesspoint_url: str = "",
        region: str = "cn-beijing"
    ):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        self.accesspoint_url = accesspoint_url
        self.region = region
        self.is_configured = bool(access_key_id and access_key_secret and endpoint and bucket_name)
        
        self._v2_client = None
        
        if self.is_configured:
            auth = oss2.Auth(access_key_id, access_key_secret)
            self.bucket = oss2.Bucket(auth, endpoint, bucket_name)

    def _get_v2_client(self) -> oss_v2.Client:
        """懒加载初始化 V2 SDK 客户端"""
        if self._v2_client is None:
            credentials_provider = oss_v2.credentials.StaticCredentialsProvider(
                access_key_id=self.access_key_id,
                access_key_secret=self.access_key_secret
            )
            config = oss_v2.config.load_default()
            config.credentials_provider = credentials_provider
            config.region = self.region
            config.endpoint = self.endpoint
            self._v2_client = oss_v2.Client(config)
        return self._v2_client

    async def upload_file(
        self,
        file_bytes: bytes,
        filename: str,
        folder: str = "audio",
        content_type: Optional[str] = None,
        multipart_threshold: int = DEFAULT_MULTIPART_THRESHOLD,
        part_size: int = DEFAULT_PART_SIZE
    ) -> str:
        """
        上传文件到 OSS，自动选择简单上传或分片上传

        Args:
            file_bytes: 文件字节数据
            filename: 原始文件名
            folder: OSS 中的文件夹路径
            content_type: 文件 MIME 类型
            multipart_threshold: 触发分片上传的文件大小阈值（默认 100MB）
            part_size: 分片大小（默认 10MB）

        Returns:
            文件的访问 URL
        """
        if not self.is_configured:
            raise Exception("OSS 服务未配置，请设置 OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_ENDPOINT, OSS_BUCKET_NAME")

        ext = os.path.splitext(filename)[1]
        unique_filename = f"{folder}/{datetime.now().strftime('%Y%m%d')}/{uuid.uuid4().hex}{ext}"

        try:
            if len(file_bytes) >= multipart_threshold:
                logger.info(f"File size {len(file_bytes)} bytes >= threshold {multipart_threshold}, using multipart upload")
                return await self._upload_multipart(
                    file_bytes, unique_filename, content_type, part_size
                )
            else:
                logger.info(f"File size {len(file_bytes)} bytes < threshold {multipart_threshold}, using simple upload")
                return await self._upload_simple(
                    file_bytes, unique_filename, content_type
                )

        except oss2.exceptions.OssError as e:
            logger.error(f"OSS 上传失败: {e}")
            raise Exception(f"OSS 上传失败: {str(e)}")
        except Exception as e:
            logger.error(f"文件上传错误: {e}")
            raise Exception(f"文件上传错误: {str(e)}")

    async def _upload_simple(
        self,
        file_bytes: bytes,
        object_key: str,
        content_type: Optional[str] = None
    ) -> str:
        """简单上传（适用于小文件）"""
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type

        self.bucket.put_object(object_key, file_bytes, headers=headers)
        file_url = self._build_url(object_key)
        logger.info(f"简单上传成功: {file_url}")
        return file_url

    async def _upload_multipart(
        self,
        file_bytes: bytes,
        object_key: str,
        content_type: Optional[str] = None,
        part_size: int = DEFAULT_PART_SIZE
    ) -> str:
        """分片上传（适用于大文件）"""
        client = self._get_v2_client()
        file_size = len(file_bytes)

        # 步骤1：初始化分片上传
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type

        init_request = oss_v2.InitiateMultipartUploadRequest(
            bucket=self.bucket_name,
            key=object_key,
            headers=headers
        )
        initiate_result = client.initiate_multipart_upload(init_request)
        upload_id = initiate_result.upload_id

        logger.info(f"初始化分片上传成功, upload_id: {upload_id}, file_size: {file_size}")

        upload_parts = []
        part_number = 1
        offset = 0

        try:
            # 步骤2：上传分片
            while offset < file_size:
                current_part_size = min(part_size, file_size - offset)
                part_data = file_bytes[offset:offset + current_part_size]

                part_result = client.upload_part(
                    oss_v2.UploadPartRequest(
                        bucket=self.bucket_name,
                        key=object_key,
                        upload_id=upload_id,
                        part_number=part_number,
                        body=io.BytesIO(part_data)
                    )
                )

                logger.info(
                    f"分片 {part_number} 上传成功, "
                    f"size: {current_part_size}, "
                    f"ETag: {part_result.etag}"
                )

                upload_parts.append(oss_v2.UploadPart(
                    part_number=part_number,
                    etag=part_result.etag
                ))

                offset += current_part_size
                part_number += 1

            # 步骤3：完成分片上传
            upload_parts.sort(key=lambda p: p.part_number)

            complete_result = client.complete_multipart_upload(
                oss_v2.CompleteMultipartUploadRequest(
                    bucket=self.bucket_name,
                    key=object_key,
                    upload_id=upload_id,
                    complete_multipart_upload=oss_v2.CompleteMultipartUpload(
                        parts=upload_parts
                    )
                )
            )

            file_url = self._build_url(object_key)
            logger.info(
                f"分片上传完成, 总分片数: {len(upload_parts)}, "
                f"ETag: {complete_result.etag}, URL: {file_url}"
            )
            return file_url

        except Exception as e:
            # 分片上传失败，取消上传清理碎片
            logger.error(f"分片上传失败，正在取消上传: {e}")
            try:
                client.abort_multipart_upload(
                    oss_v2.AbortMultipartUploadRequest(
                        bucket=self.bucket_name,
                        key=object_key,
                        upload_id=upload_id
                    )
                )
                logger.info(f"已取消分片上传: {upload_id}")
            except Exception as abort_err:
                logger.error(f"取消分片上传失败: {abort_err}")
            raise Exception(f"分片上传失败: {str(e)}")

    def _build_url(self, object_key: str) -> str:
        """构建文件访问 URL"""

        base_url = f"https://{self.bucket_name}.{self.endpoint}"
        return f"{base_url}/{object_key}"
