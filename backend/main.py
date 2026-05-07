import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from services.transcriber import TranscriberService
from services.summarizer import SummarizerService
from services.oss import OSSService
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Say API", description="语音转录和文本摘要服务（云服务代理）")

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化云服务
transcriber_service = TranscriberService(
    api_key=os.getenv("DASHSCOPE_API_KEY") or os.getenv("TRANSCRIBE_API_KEY", ""),
    model=os.getenv("TRANSCRIBE_MODEL", "fun-asr-realtime")
)

summarizer_service = SummarizerService(
    api_key=os.getenv("SUMMARIZE_API_KEY", ""),
    base_url=os.getenv("SUMMARIZE_BASE_URL", ""),
    model=os.getenv("SUMMARIZE_MODEL", "deepseek-v4-pro")
)

oss_service = OSSService(
    access_key_id=os.getenv("OSS_ACCESS_KEY_ID", ""),
    access_key_secret=os.getenv("OSS_ACCESS_KEY_SECRET", ""),
    endpoint=os.getenv("OSS_ENDPOINT", "oss-cn-beijing.aliyuncs.com"),
    bucket_name=os.getenv("OSS_BUCKET_NAME", "gediao9"),
    accesspoint_url=os.getenv("OSS_ACCESSPOINT_URL", ""),
    region="cn-beijing"
)

# 请求模型
class SummarizeRequest(BaseModel):
    text: str
    template_name: str = "summarize"
    model: Optional[str] = "default"
    max_tokens: int = 1024
    temperature: float = 0.3

# 响应模型
class TranscribeResponse(BaseModel):
    text: str
    chunks: list = []
    language: str = "auto"

class SummarizeResponse(BaseModel):
    summary: str
    model: str
    template: str

class UploadResponse(BaseModel):
    url: str
    filename: str
    size: int

class AsyncTranscribeRequest(BaseModel):
    audio_url: str

class AsyncTranscribeResponse(BaseModel):
    task_id: str
    status: str

class TranscribeStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None
    message: Optional[str] = None

@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...), language: Optional[str] = None):
    """
    接收音频文件，通过云服务返回转录文本（同步模式）
    支持格式: wav, mp3, webm, opus, m4a, ogg 等
    """
    try:
        audio_bytes = await audio.read()
        result = await transcriber_service.transcribe(audio_bytes, language)
        return TranscribeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"转录失败: {str(e)}")

@app.post("/transcribe-async", response_model=AsyncTranscribeResponse)
async def transcribe_async(request: AsyncTranscribeRequest):
    """
    提交异步转录任务（使用 fun-asr 批量模式）
    适用于 OSS 等 HTTP/HTTPS 可访问的音频文件 URL
    提交后立即返回 task_id，通过 /transcribe-status/{task_id} 查询结果
    """
    try:
        result = await transcriber_service.submit_async_transcription(request.audio_url)
        return AsyncTranscribeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交转录任务失败: {str(e)}")

@app.get("/transcribe-status/{task_id}", response_model=TranscribeStatusResponse)
async def get_transcribe_status(task_id: str):
    """
    查询异步转录任务状态
    状态说明:
    - PENDING: 任务排队中
    - RUNNING: 任务处理中
    - SUCCEEDED: 任务完成，result 字段包含转录结果
    - FAILED: 任务失败，message 字段包含错误信息
    """
    try:
        result = await transcriber_service.get_transcription_status(task_id)
        return TranscribeStatusResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询任务状态失败: {str(e)}")

@app.post("/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest):
    """
    通过云服务生成文本摘要
    支持使用 templates.yaml 中的提示词模板
    """
    try:
        result = await summarizer_service.summarize_with_template(
            text=request.text,
            template_name=request.template_name,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        return SummarizeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"摘要生成失败: {str(e)}")

@app.post("/upload", response_model=UploadResponse)
async def upload_to_oss(
    file: UploadFile = File(...),
    folder: Optional[str] = "audio",
    multipart_threshold: Optional[int] = None
):
    """
    上传文件到阿里云 OSS
    支持音频、视频、文档等格式
    大文件（>= 100MB）自动使用分片上传
    """
    try:
        file_bytes = await file.read()
        kwargs = {
            "file_bytes": file_bytes,
            "filename": file.filename or "unknown",
            "folder": folder,
            "content_type": file.content_type
        }
        if multipart_threshold is not None:
            kwargs["multipart_threshold"] = multipart_threshold

        file_url = await oss_service.upload_file(**kwargs)
        return UploadResponse(
            url=file_url,
            filename=file.filename or "unknown",
            size=len(file_bytes)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "transcribe_service": "configured" if transcriber_service.is_configured else "not configured",
        "summarize_service": "configured" if summarizer_service.is_configured else "not configured",
        "oss_service": "configured" if oss_service.is_configured else "not configured"
    }
