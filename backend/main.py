import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from services.transcriber import TranscriberService
from services.summarizer import SummarizerService
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
    api_key=os.getenv("TRANSCRIBE_API_KEY", ""),
    api_url=os.getenv("TRANSCRIBE_API_URL", "")
)

summarizer_service = SummarizerService(
    api_key=os.getenv("SUMMARIZE_API_KEY", ""),
    api_url=os.getenv("SUMMARIZE_API_URL", "")
)

# 请求模型
class SummarizeRequest(BaseModel):
    text: str
    model: Optional[str] = "default"
    max_length: int = 150
    min_length: int = 40

# 响应模型
class TranscribeResponse(BaseModel):
    text: str
    chunks: list = []
    language: str = "auto"

class SummarizeResponse(BaseModel):
    summary: str
    model: str

@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...), language: Optional[str] = None):
    """
    接收音频文件，通过云服务返回转录文本
    支持格式: wav, mp3, webm, m4a 等
    """
    try:
        audio_bytes = await audio.read()
        result = await transcriber_service.transcribe(audio_bytes, language)
        return TranscribeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"转录失败: {str(e)}")

@app.post("/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest):
    """
    通过云服务生成文本摘要
    """
    try:
        result = await summarizer_service.summarize(
            text=request.text,
            model=request.model,
            max_length=request.max_length,
            min_length=request.min_length
        )
        return SummarizeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"摘要生成失败: {str(e)}")

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "transcribe_service": "configured" if transcriber_service.is_configured else "not configured",
        "summarize_service": "configured" if summarizer_service.is_configured else "not configured"
    }
