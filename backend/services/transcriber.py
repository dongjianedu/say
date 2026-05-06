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
import subprocess
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
        sample_rate = self._detect_sample_rate(audio_bytes, audio_format)
        logger.info(f"Detected audio format: {audio_format}, sample_rate: {sample_rate}")

        # Recognition API 仅支持 WAV/PCM，压缩格式需先转换
        needs_conversion = audio_format in ("webm", "opus", "ogg", "m4a", "mp3")
        
        input_path = None
        wav_path = None
        try:
            # 写入原始文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_format}") as tmp:
                tmp.write(audio_bytes)
                input_path = tmp.name

            if needs_conversion:
                # 使用 ffmpeg 转换为 16kHz 单声道 WAV
                wav_path = self._convert_to_wav(input_path, audio_format)
                process_path = wav_path
                process_format = "wav"
                process_sample_rate = 16000
            else:
                process_path = input_path
                process_format = audio_format
                process_sample_rate = sample_rate

            recognition = Recognition(
                model=self.model,
                format=process_format,
                sample_rate=process_sample_rate,
                callback=None,
            )

            result = recognition.call(process_path)
            logger.debug(f"Recognition result object: {result}")
            
            sentence_list = result.get_sentence()
            if sentence_list is None:
                error_msg = result.get('message', '') or result.get('code', '') or 'No transcription result'
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
            for path in [input_path, wav_path]:
                if path and os.path.exists(path):
                    os.remove(path)

    def _convert_to_wav(self, input_path: str, original_format: str) -> str:
        """使用 ffmpeg 将压缩音频转换为 16kHz 单声道 WAV"""
        wav_path = input_path + ".converted.wav"
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", input_path,
                "-ar", "16000", "-ac", "1",
                "-c:a", "pcm_s16le",
                wav_path
            ],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            logger.error(f"ffmpeg conversion failed: {result.stderr}")
            raise Exception(f"音频格式转换失败: {result.stderr[:200]}")
        logger.info(f"Converted {original_format} to WAV successfully")
        return wav_path

    def _detect_format(self, audio_bytes: bytes) -> str:
        """根据文件头检测音频格式"""
        if len(audio_bytes) >= 4 and audio_bytes[:4] == b'RIFF':
            return "wav"
        elif len(audio_bytes) >= 4 and audio_bytes[:4] == b'\x1a\x45\xdf\xa3':
            return "webm"
        elif len(audio_bytes) >= 8 and audio_bytes[:8] == b'OpusHead':
            return "opus"
        elif len(audio_bytes) >= 2 and (audio_bytes[:2] == b'\xff\xfb' or audio_bytes[:2] == b'\xff\xf3'):
            return "mp3"
        elif len(audio_bytes) >= 4 and audio_bytes[:4] == b'OggS':
            return "ogg"
        elif len(audio_bytes) >= 8 and audio_bytes[:8] == b'\x00\x00\x00\x1c\x66\x74\x79\x70':
            return "m4a"
        else:
            return "wav"

    def _detect_sample_rate(self, audio_bytes: bytes, audio_format: str = "wav") -> int:
        """检测音频采样率"""
        if audio_format == "wav" and audio_bytes[:4] == b'RIFF' and len(audio_bytes) > 28:
            try:
                sample_rate = struct.unpack('<I', audio_bytes[24:28])[0]
                if 8000 <= sample_rate <= 48000:
                    return sample_rate
            except Exception:
                pass

        if audio_format in ("webm", "opus", "ogg", "m4a", "mp3"):
            return self._get_sample_rate_via_ffprobe(audio_bytes, audio_format)

        return 16000

    def _get_sample_rate_via_ffprobe(self, audio_bytes: bytes, audio_format: str) -> int:
        """通过 ffprobe 获取压缩音频的实际采样率"""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{audio_format}") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-select_streams", "a:0",
                    "-show_entries", "stream=sample_rate",
                    "-of", "csv=p=0",
                    tmp_path
                ],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                sample_rate = int(result.stdout.strip())
                if 8000 <= sample_rate <= 48000:
                    logger.info(f"Detected sample rate via ffprobe: {sample_rate}Hz")
                    return sample_rate

            logger.warning(f"ffprobe failed or invalid sample rate, using default 48000Hz for {audio_format}")
            return 48000

        except Exception as e:
            logger.warning(f"ffprobe error: {e}, using default 48000Hz for {audio_format}")
            return 48000
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

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
