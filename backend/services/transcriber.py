"""
语音识别服务 - 阿里云 DashScope 单文件实时识别
支持单音频文件语音识别，支持多种音频格式
文档: https://help.aliyun.com/document_detail/2712535.html
"""

import os
import json
import logging
import tempfile
import struct
from http import HTTPStatus
from typing import Optional

import dashscope
from dashscope.audio.asr import Recognition
from dashscope.api_entities.dashscope_response import TranscriptionResponse

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "fun-asr-realtime"
POLL_INTERVAL = 3
MAX_WAIT_TIME = 600


class TranscriberService:
    def __init__(self, api_key: str = "", api_url: str = "", model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.api_url = api_url
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
        通过 DashScope Recognition API 进行单文件实时转录

        Args:
            audio_bytes: 音频文件字节数据
            language: 语言代码 (如 "zh", "en")

        Returns:
            {"text": "转录文本", "chunks": [...], "language": "语言"}
        """
        if not self.is_configured:
            raise Exception("转录服务未配置，请设置 DASHSCOPE_API_KEY 或 TRANSCRIBE_API_KEY")

        audio_format = self._detect_format(audio_bytes)
        sample_rate = self._detect_sample_rate(audio_bytes)
        logger.info(f"Detected audio format: {audio_format}, sample_rate: {sample_rate}")

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_format}") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            recognition = Recognition(
                model=self.model,
                format=audio_format,
                sample_rate=sample_rate,
                callback=None,
            )

            result = recognition.call(tmp_path)
            logger.debug(f"Recognition result object: {result}")
            
            sentence_list = result.get_sentence()
            if sentence_list is None:
                error_msg = getattr(result, 'message', None) or getattr(result, 'status_message', 'No transcription result')
                logger.warning(f"Recognition returned no sentences. Result: {result}")
                raise Exception(f"转录失败: {error_msg}")

            full_text = ""
            chunks = []
            detected_language = "auto"

            for sentence in sentence_list:
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

            logger.info(f"Transcription successful, text length: {len(full_text)}")
            return {
                "text": full_text,
                "chunks": chunks,
                "language": detected_language
            }

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise Exception(f"云服务转录失败: {str(e)}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _detect_format(self, audio_bytes: bytes) -> str:
        if len(audio_bytes) >= 4 and audio_bytes[:4] == b'RIFF':
            return "wav"
        elif len(audio_bytes) >= 2 and (audio_bytes[:2] == b'\xff\xfb' or audio_bytes[:2] == b'\xff\xf3'):
            return "mp3"
        elif len(audio_bytes) >= 4 and audio_bytes[:4] == b'OggS':
            return "ogg"
        elif len(audio_bytes) >= 8 and audio_bytes[:8] == b'\x00\x00\x00\x1c\x66\x74\x79\x70':
            return "m4a"
        else:
            return "wav"

    def _detect_sample_rate(self, audio_bytes: bytes) -> int:
        if audio_bytes[:4] == b'RIFF' and len(audio_bytes) > 28:
            try:
                sample_rate = struct.unpack('<I', audio_bytes[24:28])[0]
                if 8000 <= sample_rate <= 48000:
                    return sample_rate
            except Exception:
                pass
        return 16000

    async def transcribe_from_url(
        self,
        audio_url: str,
        language: Optional[str] = None
    ) -> dict:
        if not self.is_configured:
            raise Exception("转录服务未配置")

        response = dashscope.audio.asr.Transcription.async_call(
            model=self.model,
            file_urls=[audio_url]
        )

        if response.status_code != HTTPStatus.OK:
            raise Exception(f"提交转录任务失败: {response.code} - {response.message}")

        task_id = response.output.task_id
        logger.info(f"转录任务已提交，task_id: {task_id}, url: {audio_url}")

        result = self._wait_for_result(task_id)
        return self._parse_result(result)

    def _wait_for_result(self, task_id: str) -> TranscriptionResponse:
        import time
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
                results = response.output.get("results", [])
                error_msg = "未知错误"
                if results:
                    error_msg = results[0].get("message", response.output.get("message", "未知错误"))
                raise Exception(f"转录任务失败: {error_msg}")
            elif task_status in ["PENDING", "RUNNING"]:
                logger.debug(f"转录任务进行中: {task_id}, 状态: {task_status}")
                time.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
            else:
                raise Exception(f"未知任务状态: {task_status}")

        raise Exception(f"转录任务超时（{MAX_WAIT_TIME}秒）: {task_id}")

    def _parse_result(self, response: TranscriptionResponse) -> dict:
        results = response.output.get("results", [])
        if not results:
            return {"text": "", "chunks": [], "language": "auto"}

        result = results[0]
        transcription_url = result.get("transcription_url")

        if not transcription_url:
            return {"text": "", "chunks": [], "language": "auto"}

        import requests
        try:
            resp = requests.get(transcription_url, timeout=30)
            resp.raise_for_status()
            result_data = resp.json()
        except Exception as e:
            logger.error(f"下载转录结果失败: {e}")
            raise Exception(f"下载转录结果失败: {str(e)}")

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
