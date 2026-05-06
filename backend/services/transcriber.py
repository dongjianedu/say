"""
语音识别服务 - 阿里云百炼 DashScope 批量异步转录
支持批量音视频文件语音识别，支持多种音频格式
文档: https://help.aliyun.com/document_detail/2712535.html
"""

import os
import time
import json
import logging
import tempfile
from http import HTTPStatus
from typing import Optional
from pathlib import Path

import dashscope
from dashscope.api_entities.dashscope_response import TranscriptionResponse

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "fun-asr"
POLL_INTERVAL = 3  # 轮询间隔（秒）
MAX_WAIT_TIME = 600  # 最大等待时间（秒）


class TranscriberService:
    def __init__(self, api_key: str = "", api_url: str = "", model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.api_url = api_url  # 保留兼容，DashScope 不需要
        self.model = model
        self.is_configured = bool(api_key)
        if self.is_configured:
            dashscope.api_key = api_key

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None
    ) -> dict:
        """
        调用阿里云 DashScope 异步转录音频文件

        Args:
            audio_bytes: 音频文件字节数据
            language: 语言代码 (如 "zh", "en")，DashScope 自动检测时可忽略

        Returns:
            {"text": "转录文本", "chunks": [...], "language": "语言"}
        """
        if not self.is_configured:
            raise Exception("转录服务未配置，请设置 DASHSCOPE_API_KEY 或 TRANSCRIBE_API_KEY")

        # 将音频字节数据写入临时文件并上传获取 URL
        # 注意：DashScope 异步 API 需要可访问的文件 URL
        # 这里使用本地文件路径方式（SDK 支持本地文件自动上传）
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            # 提交异步转录任务
            response = dashscope.audio.asr.Transcription.async_call(
                model=self.model,
                file_urls=[tmp_path]
            )

            if response.status_code != HTTPStatus.OK:
                raise Exception(f"提交转录任务失败: {response.code} - {response.message}")

            task_id = response.output.task_id
            logger.info(f"转录任务已提交，task_id: {task_id}")

            # 等待并获取转录结果
            result = self._wait_for_result(task_id)

            # 解析结果
            return self._parse_result(result)

        finally:
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def transcribe_from_url(
        self,
        audio_url: str,
        language: Optional[str] = None
    ) -> dict:
        """
        调用阿里云 DashScope 异步转录音频文件（通过 URL）

        Args:
            audio_url: 音频文件的 HTTP/HTTPS URL
            language: 语言代码 (如 "zh", "en")，DashScope 自动检测时可忽略

        Returns:
            {"text": "转录文本", "chunks": [...], "language": "语言"}
        """
        if not self.is_configured:
            raise Exception("转录服务未配置，请设置 DASHSCOPE_API_KEY 或 TRANSCRIBE_API_KEY")

        # 提交异步转录任务（直接使用 URL）
        response = dashscope.audio.asr.Transcription.async_call(
            model=self.model,
            file_urls=[audio_url]
        )

        if response.status_code != HTTPStatus.OK:
            raise Exception(f"提交转录任务失败: {response.code} - {response.message}")

        task_id = response.output.task_id
        logger.info(f"转录任务已提交，task_id: {task_id}, url: {audio_url}")

        # 等待并获取转录结果
        result = self._wait_for_result(task_id)

        # 解析结果
        return self._parse_result(result)

    def _wait_for_result(self, task_id: str) -> TranscriptionResponse:
        """
        等待转录任务完成并返回结果

        Args:
            task_id: 转录任务 ID

        Returns:
            TranscriptionResponse 对象
        """
        elapsed = 0
        while elapsed < MAX_WAIT_TIME:
            response = dashscope.audio.asr.Transcription.wait(task=task_id)

            if response.status_code != HTTPStatus.OK:
                raise Exception(f"获取转录结果失败: {response.code} - {response.message}")

            task_status = response.output.task_status
            if task_status == "SUCCEEDED":
                logger.info(f"转录任务完成: {task_id}")
                return response
            elif task_status == "FAILED":
                error_msg = response.output.get("error_message", "未知错误")
                raise Exception(f"转录任务失败: {error_msg}")
            elif task_status in ["PENDING", "RUNNING"]:
                logger.debug(f"转录任务进行中: {task_id}, 状态: {task_status}")
                time.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
            else:
                raise Exception(f"未知任务状态: {task_status}")

        raise Exception(f"转录任务超时（{MAX_WAIT_TIME}秒）: {task_id}")

    def _parse_result(self, response: TranscriptionResponse) -> dict:
        """
        解析转录结果

        Args:
            response: TranscriptionResponse 对象

        Returns:
            标准化字典 {"text": "...", "chunks": [...], "language": "..."}
        """
        results = response.output.get("results", [])
        if not results:
            return {"text": "", "chunks": [], "language": "auto"}

        # 获取第一个文件的结果
        result = results[0]
        transcription_url = result.get("transcription_url")

        if not transcription_url:
            return {"text": "", "chunks": [], "language": "auto"}

        # 下载并解析转录结果 JSON
        import requests
        try:
            resp = requests.get(transcription_url, timeout=30)
            resp.raise_for_status()
            result_data = resp.json()
        except Exception as e:
            logger.error(f"下载转录结果失败: {e}")
            raise Exception(f"下载转录结果失败: {str(e)}")

        # 提取文本和分块
        full_text = ""
        chunks = []
        detected_language = "auto"

        transcripts = result_data.get("transcripts", [])
        for transcript in transcripts:
            for sentence in transcript.get("sentences", []):
                text = sentence.get("text", "")
                full_text += text
                chunks.append({
                    "text": text,
                    "start_time": sentence.get("begin_time", 0),
                    "end_time": sentence.get("end_time", 0),
                    "language": sentence.get("language", "")
                })
                if sentence.get("language"):
                    detected_language = sentence["language"]

        return {
            "text": full_text,
            "chunks": chunks,
            "language": detected_language
        }
