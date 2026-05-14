# Say API

语音转录、文本摘要和文件上传服务。基于 FastAPI 构建，代理阿里云 DashScope 语音识别和 LLM 服务。

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 启动服务
uvicorn main:app --host 0.0.0.0 --port 8000
```

服务启动后访问 `http://localhost:8000/docs` 查看交互式 API 文档。

---

## API 接口说明

### 1. 语音转录接口 `POST /transcribe`

接收音频文件，返回转录文本及带时间戳的分句结果。

**请求参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `audio` | file | 是 | 音频文件（支持 wav、mp3、webm、opus、ogg、m4a 等格式） |
| `language` | string | 否 | 语言代码，如 `zh`（中文）、`en`（英文），不传则自动检测 |

**响应格式**

```json
{
  "text": "完整转录文本",
  "chunks": [
    {
      "text": "分句文本",
      "start_time": 0,
      "end_time": 1920,
      "language": ""
    }
  ],
  "language": "auto"
}
```

**字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | string | 完整转录文本 |
| `chunks` | array | 分句列表，每句包含文本和时间戳 |
| `chunks[].text` | string | 分句文本 |
| `chunks[].start_time` | number | 开始时间（毫秒） |
| `chunks[].end_time` | number | 结束时间（毫秒） |
| `language` | string | 检测到的语言 |

**curl 示例**

```bash
# 基本转录（自动检测语言）
curl -X POST "http://localhost:8000/transcribe" \
  -F "audio=@/path/to/recording.wav"

# 指定语言为中文
curl -X POST "http://localhost:8000/transcribe?language=zh" \
  -F "audio=@/path/to/recording.mp3"

# 转录浏览器录音（webm/opus 格式）
curl -X POST "http://localhost:8000/transcribe" \
  -F "audio=@/path/to/browser-recording.webm"
```

---

### 1.1 异步转录接口 `POST /transcribe-async`

提交异步转录任务，适用于 OSS 等 HTTP/HTTPS 可访问的音频文件 URL。使用 `fun-asr` 模型进行批量处理，支持最多 100 个文件/任务。

**请求参数**（JSON Body）

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `audio_url` | string | 是 | 音频文件的 HTTP/HTTPS URL（如 OSS 公开链接） |

**响应格式**

```json
{
  "task_id": "d66846c1-3fc9-4fc7-867c-dce29ec7746b",
  "status": "PENDING"
}
```

**curl 示例**

```bash
# 提交异步转录任务
curl -X POST "http://localhost:8000/transcribe-async" \
  -H "Content-Type: application/json" \
  -d '{
    "audio_url": "https://gediao9.oss-cn-beijing.aliyuncs.com/audio/20260507/xxx.wav"
  }'
```

---

### 1.2 查询转录任务状态 `GET /transcribe-status/{task_id}`

查询异步转录任务的执行状态和结果。

**路径参数**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 异步任务 ID（由 /transcribe-async 返回） |

**响应格式**

```json
{
  "task_id": "d66846c1-3fc9-4fc7-867c-dce29ec7746b",
  "status": "SUCCEEDED",
  "result": {
    "text": "hello world这里是阿里巴巴语音实验室。",
    "chunks": [
      {
        "text": "hello world这里是阿里巴巴语音实验室。",
        "start_time": 520,
        "end_time": 4320,
        "language": ""
      }
    ],
    "language": "auto"
  },
  "message": null
}
```

**状态说明**

| 状态 | 说明 |
|------|------|
| `PENDING` | 任务排队中 |
| `RUNNING` | 任务处理中 |
| `SUCCEEDED` | 任务完成，`result` 字段包含转录结果 |
| `FAILED` | 任务失败，`message` 字段包含错误信息 |

**curl 示例**

```bash
# 查询任务状态
curl "http://localhost:8000/transcribe-status/d66846c1-3fc9-4fc7-867c-dce29ec7746b"

# 轮询直到完成（示例脚本）
TASK_ID=$(curl -s -X POST "http://localhost:8000/transcribe-async" \
  -H "Content-Type: application/json" \
  -d '{"audio_url": "https://xxx.wav"}' | jq -r '.task_id')

while true; do
  STATUS=$(curl -s "http://localhost:8000/transcribe-status/$TASK_ID" | jq -r '.status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ]; then
    break
  fi
  sleep 3
done

# 获取完整结果
curl -s "http://localhost:8000/transcribe-status/$TASK_ID" | jq '.result.text'
```

---

### 2. 文本摘要接口 `POST /summarize`

使用 LLM 对输入文本生成摘要，支持多种提示词模板。

**请求参数**（JSON Body）

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `text` | string | 是 | - | 需要摘要的文本内容 |
| `template_name` | string | 否 | `summarize` | 提示词模板名称 |
| `model` | string | 否 | `default` | 模型名称，不传或使用 `default` 时使用服务端配置的默认模型（如 `deepseek-v4-pro`） |
| `max_tokens` | integer | 否 | `1024` | 最大输出 token 数 |
| `temperature` | float | 否 | `0.3` | 温度参数（0-1），越低越确定 |

**可用模板**

| 模板名称 | 说明 | 适用场景 |
|----------|------|----------|
| `summarize` | 通用摘要 | 一般文本摘要 |
| `interview_summary` | 人物专访摘要 | 采访录音转录文本，按"格调九问"结构整理 |
| `meeting_summary` | 会议纪要摘要 | 会议记录提取议题、决策、待办 |
| `article_summary` | 文章摘要 | 文章核心论点提取 |
| `chat` | 通用对话 | 问答/对话场景 |

**响应格式**

```json
{
  "summary": "摘要文本内容",
  "model": "deepseek-v4-pro",
  "template": "interview_summary"
}
```

**curl 示例**

```bash
# 使用默认模型（不传 model 或传 "default"）
curl -X POST "http://localhost:8000/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "这是一段需要摘要的长文本内容..."
  }'

# 使用人物专访模板
curl -X POST "http://localhost:8000/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "采访录音的完整转录文本...",
    "template_name": "interview_summary",
    "max_tokens": 4096
  }'

# 使用自定义模型（如 qwen-plus、qwen-turbo 等）
curl -X POST "http://localhost:8000/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "这是一段文本...",
    "template_name": "meeting_summary",
    "model": "qwen-plus",
    "max_tokens": 2048,
    "temperature": 0.5
  }'
```

---

### 3. 文件上传接口 `POST /upload`

上传文件到阿里云 OSS，返回可访问的文件 URL。支持自动分片上传。

**上传策略：**
- 小文件（< 100MB）：使用简单上传
- 大文件（>= 100MB）：自动切换为分片上传（10MB/片）

**请求参数**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `file` | file | 是 | - | 要上传的文件 |
| `folder` | string | 否 | `audio` | OSS 中的文件夹路径 |
| `multipart_threshold` | integer | 否 | `104857600` (100MB) | 触发分片上传的文件大小阈值（字节） |

**响应格式**

```json
{
  "url": "https://gediao9-xxx.oss-cn-beijing.oss-accesspoint.aliyuncs.com/audio/20260506/abc123.wav",
  "filename": "recording.wav",
  "size": 1234567
}
```

**字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `url` | string | 文件访问 URL |
| `filename` | string | 原始文件名 |
| `size` | integer | 文件大小（字节） |

**curl 示例**

```bash
# 上传音频文件到默认目录（简单上传）
curl -X POST "http://localhost:8000/upload" \
  -F "file=@/path/to/recording.wav"

# 上传到指定文件夹
curl -X POST "http://localhost:8000/upload?folder=interviews" \
  -F "file=@/path/to/interview.mp3"

# 强制使用分片上传（设置阈值为 0）
curl -X POST "http://localhost:8000/upload?folder=videos&multipart_threshold=0" \
  -F "file=@/path/to/video.mp4"

# 上传文档
curl -X POST "http://localhost:8000/upload?folder=documents" \
  -F "file=@/path/to/document.pdf"
```

---

### 4. 健康检查接口 `GET /health`

检查各服务的配置状态。

**curl 示例**

```bash
curl "http://localhost:8000/health"
```

**响应示例**

```json
{
  "status": "ok",
  "transcribe_service": "configured",
  "summarize_service": "configured",
  "oss_service": "configured"
}
```

---

## 环境变量配置

| 变量 | 说明 | 示例 |
|------|------|------|
| `DASHSCOPE_API_KEY` | 阿里云 DashScope API Key（转录服务） | `sk-xxx` |
| `TRANSCRIBE_API_KEY` | 转录服务 API Key（兼容旧配置） | `sk-xxx` |
| `TRANSCRIBE_MODEL` | 转录模型（默认 fun-asr-realtime） | `fun-asr-realtime` |
| `SUMMARIZE_API_KEY` | 摘要服务 API Key | `sk-xxx` |
| `SUMMARIZE_BASE_URL` | 摘要服务 Base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `SUMMARIZE_MODEL` | 摘要服务默认模型 | `deepseek-v4-pro` |
| `OSS_ACCESS_KEY_ID` | 阿里云 OSS AccessKey ID | `LTAI5t...` |
| `OSS_ACCESS_KEY_SECRET` | 阿里云 OSS AccessKey Secret | `xIN19v...` |
| `OSS_ENDPOINT` | OSS Endpoint | `oss-cn-beijing.aliyuncs.com` |
| `OSS_BUCKET_NAME` | OSS Bucket 名称 | `gediao9` |
| `OSS_ACCESSPOINT_URL` | OSS 接入点 URL（用于生成文件访问链接） | `https://gediao9-xxx.oss-cn-beijing.oss-accesspoint.aliyuncs.com` |

---

## 典型工作流

### 工作流 1：同步转录（短音频）

上传音频 → 转录文本 → 生成摘要：

```bash
# 1. 上传音频到 OSS
UPLOAD_RESULT=$(curl -s -X POST "http://localhost:8000/upload" \
  -F "file=@interview.wav")
AUDIO_URL=$(echo $UPLOAD_RESULT | jq -r '.url')
echo "音频已上传: $AUDIO_URL"

# 2. 转录音频（同步，适合短音频）
TRANSCRIBE_RESULT=$(curl -s -X POST "http://localhost:8000/transcribe" \
  -F "audio=@interview.wav")
TRANSCRIPT=$(echo $TRANSCRIBE_RESULT | jq -r '.text')

# 3. 使用转录文本生成人物专访摘要
SUMMARY_RESULT=$(curl -s -X POST "http://localhost:8000/summarize" \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"$TRANSCRIPT\",
    \"template_name\": \"interview_summary\",
    \"max_tokens\": 4096
  }")
echo $SUMMARY_RESULT | jq -r '.summary'
```

### 工作流 2：异步转录（长音频/OSS 文件）

上传音频 → 提交异步任务 → 轮询结果 → 生成摘要：

```bash
# 1. 上传音频到 OSS
UPLOAD_RESULT=$(curl -s -X POST "http://localhost:8000/upload" \
  -F "file=@long-interview.wav")
AUDIO_URL=$(echo $UPLOAD_RESULT | jq -r '.url')

# 2. 提交异步转录任务
SUBMIT_RESULT=$(curl -s -X POST "http://localhost:8000/transcribe-async" \
  -H "Content-Type: application/json" \
  -d "{\"audio_url\": \"$AUDIO_URL\"}")
TASK_ID=$(echo $SUBMIT_RESULT | jq -r '.task_id')
echo "任务已提交: $TASK_ID"

# 3. 轮询直到完成
while true; do
  STATUS=$(curl -s "http://localhost:8000/transcribe-status/$TASK_ID" | jq -r '.status')
  echo "状态: $STATUS"
  if [ "$STATUS" = "SUCCEEDED" ] || [ "$STATUS" = "FAILED" ]; then
    break
  fi
  sleep 3
done

# 4. 获取转录文本
TRANSCRIPT=$(curl -s "http://localhost:8000/transcribe-status/$TASK_ID" | jq -r '.result.text')

# 5. 生成摘要
SUMMARY_RESULT=$(curl -s -X POST "http://localhost:8000/summarize" \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"$TRANSCRIPT\",
    \"template_name\": \"interview_summary\",
    \"max_tokens\": 4096
  }")
echo $SUMMARY_RESULT | jq -r '.summary'
```

---

## 运行测试

```bash
# 设置环境变量
export DASHSCOPE_API_KEY=sk-xxx

# 运行所有测试
pytest tests/ -v

# 运行转录服务单元测试（使用本地测试音频）
pytest tests/test_transcriber_unit.py -v -s

# 运行转录服务集成测试（使用在线音频 URL）
pytest tests/test_transcriber_integration.py -v -s

# 运行 OSS 上传测试
pytest tests/test_oss_integration.py -v -s
```

### 测试输出示例

```
============================================================
转录服务单元测试
============================================================

测试文件: hello_world_male_16k_16bit_mono.wav
文件大小: 160814 字节
使用模型: fun-asr-realtime

============================================================
转录结果:
============================================================

检测到的语言: auto

完整转录文本:
Hello World，这里是阿里巴巴语音实验室。

分块数量: 1

分块详情:
  [1] Hello World，这里是阿里巴巴语音实验室。
      时间: 680ms - 4520ms
```
