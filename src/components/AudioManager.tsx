import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import Modal from "./modal/Modal";
import { UrlInput } from "./modal/UrlInput";
import AudioPlayer from "./AudioPlayer";
import { TranscribeButton } from "./TranscribeButton";
import Constants from "../utils/Constants";
import { Transcriber } from "../hooks/useTranscriber";
import AudioRecorder from "./AudioRecorder";

export enum AudioSource {
    URL = "URL",
    FILE = "FILE",
    RECORDING = "RECORDING",
}

interface Props {
    transcriber: Transcriber;
    onTranscriptionComplete?: (text: string, ossUrl?: string) => void;
    onAutoTranscriptionComplete?: (text: string, ossUrl: string, segmentIndex: number, isFirst: boolean) => void;
}

export function AudioManager({ transcriber, onTranscriptionComplete, onAutoTranscriptionComplete }: Props) {
    const [progress, setProgress] = useState<number | undefined>(undefined);
    const [audioData, setAudioData] = useState<{
        blob: Blob;
        url: string;
        source: AudioSource;
        mimeType: string;
    } | undefined>(undefined);
    const [audioDownloadUrl, setAudioDownloadUrl] = useState<string | undefined>(undefined);
    const [showUrlModal, setShowUrlModal] = useState(false);
    const [showRecordModal, setShowRecordModal] = useState(false);
    const [isAutoTranscribing, setIsAutoTranscribing] = useState(false);
    const [transcribingSegments, setTranscribingSegments] = useState<Record<number, string>>({});

    const isAudioLoading = progress !== undefined;
    const onAutoTranscriptionCompleteRef = useRef(onAutoTranscriptionComplete);
    const currentNoteIdRef = useRef<string | null>(null);

    useEffect(() => {
        onAutoTranscriptionCompleteRef.current = onAutoTranscriptionComplete;
    }, [onAutoTranscriptionComplete]);

    const resetAudio = useCallback(() => {
        setAudioData(undefined);
        setAudioDownloadUrl(undefined);
        currentNoteIdRef.current = null;
        setTranscribingSegments({});
    }, []);

    useEffect(() => {
        if (transcriber.output && !transcriber.isBusy && onTranscriptionComplete) {
            onTranscriptionComplete(transcriber.output.text, transcriber.output.ossUrl);
            resetAudio();
        }
    }, [transcriber.output?.text, transcriber.output?.ossUrl, transcriber.isBusy, onTranscriptionComplete, resetAudio]);

    const setAudioFromDownload = async (data: ArrayBuffer, mimeType: string) => {
        const blob = new Blob([data], { type: mimeType || "audio/*" });
        const blobUrl = URL.createObjectURL(blob);
        setAudioData({
            blob,
            url: blobUrl,
            source: AudioSource.URL,
            mimeType: mimeType || "audio/wav",
        });
    };

    const setAudioFromRecording = (data: Blob) => {
        resetAudio();
        const blobUrl = URL.createObjectURL(data);
        setAudioData({
            blob: data,
            url: blobUrl,
            source: AudioSource.RECORDING,
            mimeType: data.type || "audio/webm",
        });
        setShowRecordModal(false);
        setProgress(undefined);
    };

    const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
        const files = event.target.files;
        if (!files || files.length === 0) return;

        const file = files[0];
        const blobUrl = URL.createObjectURL(file);
        transcriber.onInputChange();
        setAudioData({
            blob: file,
            url: blobUrl,
            source: AudioSource.FILE,
            mimeType: file.type || "audio/*",
        });
    };

    const downloadAudioFromUrl = async (requestAbortController: AbortController) => {
        if (audioDownloadUrl) {
            try {
                setAudioData(undefined);
                setProgress(0);
                const { data, headers } = await axios.get(audioDownloadUrl, {
                    signal: requestAbortController.signal,
                    responseType: "arraybuffer",
                    onDownloadProgress(progressEvent) {
                        setProgress(progressEvent.progress || 0);
                    },
                });

                let mimeType = headers["content-type"];
                if (!mimeType || mimeType === "audio/wave") {
                    mimeType = "audio/wav";
                }
                setAudioFromDownload(data, mimeType);
                setShowUrlModal(false);
            } catch (error) {
                console.error("Request failed or aborted", error);
            } finally {
                setProgress(undefined);
            }
        }
    };

    useEffect(() => {
        if (audioDownloadUrl) {
            const requestAbortController = new AbortController();
            downloadAudioFromUrl(requestAbortController);
            return () => {
                requestAbortController.abort();
            };
        }
    }, [audioDownloadUrl]);

    const handleTranscribeClick = useCallback(() => {
        if (!audioData) return;
        transcriber.onInputChange();
        transcriber.start(audioData.blob);
    }, [audioData, transcriber]);

    const handleExportAudio = useCallback(async () => {
        if (!audioData) return;

        try {
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
            const url = URL.createObjectURL(audioData.blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `recording-${timestamp}.webm`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Error exporting audio:', error);
        }
    }, [audioData]);

    const handleSegmentAvailable = useCallback((blob: Blob, index: number) => {
        setIsAutoTranscribing(true);
        console.log(`Audio segment ${index + 1} available, size: ${blob.size} bytes`);

        setTranscribingSegments(prev => ({ ...prev, [index]: 'uploading' }));

        const processSegment = async () => {
            try {
                const uploadFormData = new FormData();
                uploadFormData.append('file', blob, `segment-${index}.webm`);

                setTranscribingSegments(prev => ({ ...prev, [index]: 'uploading' }));

                const uploadResponse = await fetch(Constants.UPLOAD_API_URL, {
                    method: 'POST',
                    body: uploadFormData,
                });

                if (!uploadResponse.ok) {
                    throw new Error(`Upload failed! status: ${uploadResponse.status}`);
                }

                const uploadResult = await uploadResponse.json();
                const ossUrl = uploadResult.url;

                setTranscribingSegments(prev => ({ ...prev, [index]: 'transcribing' }));

                const asyncResponse = await fetch(Constants.TRANSCRIBE_ASYNC_API_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ audio_url: ossUrl }),
                });

                if (!asyncResponse.ok) {
                    throw new Error(`Submit async task failed! status: ${asyncResponse.status}`);
                }

                const asyncResult = await asyncResponse.json();
                const taskId = asyncResult.task_id;

                let pollCount = 0;
                const maxPolls = 200;

                while (pollCount < maxPolls) {
                    await new Promise(resolve => setTimeout(resolve, 3000));

                    try {
                        const statusRes = await fetch(`${Constants.TRANSCRIBE_STATUS_API_URL}/${taskId}`);
                        const statusData = await statusRes.json();

                        if (statusData.status === 'SUCCEEDED') {
                            const text = statusData.result?.text || '';
                            if (onAutoTranscriptionCompleteRef.current && text) {
                                const isFirst = index === 0;
                                onAutoTranscriptionCompleteRef.current(text, ossUrl, index, isFirst);
                            }
                            setTranscribingSegments(prev => {
                                const next = { ...prev };
                                delete next[index];
                                return next;
                            });
                            break;
                        } else if (statusData.status === 'FAILED') {
                            throw new Error(statusData.message || 'Transcription failed');
                        }
                    } catch (err) {
                        if (pollCount >= 3) {
                            console.error(`Poll error for segment ${index}:`, err);
                            setTranscribingSegments(prev => {
                                const next = { ...prev };
                                delete next[index];
                                return next;
                            });
                            break;
                        }
                    }

                    pollCount++;
                }
            } catch (error) {
                console.error(`Error processing segment ${index}:`, error);
                setTranscribingSegments(prev => {
                    const next = { ...prev };
                    delete next[index];
                    return next;
                });
            }
        };

        processSegment();
    }, []);

    return (
        <div className="space-y-6">

            {!audioData && (
                <div className="flex flex-col items-center gap-4">
                    <button
                        onClick={() => setShowRecordModal(true)}
                        className="w-full max-w-md px-6 py-4 bg-blue-500 hover:bg-blue-600 text-white rounded-xl shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all text-lg font-semibold flex items-center justify-center gap-3"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                        </svg>
                        开始录音采访
                    </button>

                    <div className="flex gap-4 w-full max-w-md">
                        <button
                            onClick={() => setShowUrlModal(true)}
                            className="flex-1 px-4 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors flex items-center justify-center gap-2"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
                            </svg>
                            从链接导入
                        </button>

                        <label className="flex-1 px-4 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors flex items-center justify-center gap-2 cursor-pointer">
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            上传文件
                            <input
                                type="file"
                                accept="audio/*"
                                onChange={handleFileUpload}
                                className="hidden"
                            />
                        </label>
                    </div>
                </div>
            )}

            {isAudioLoading && (
                <div className="w-full bg-gray-200 rounded-full h-1">
                    <div
                        className="bg-blue-600 h-1 rounded-full transition-all duration-100"
                        style={{ width: `${Math.round(progress! * 100)}%` }}
                    />
                </div>
            )}

            {audioData && (
                <div className="space-y-4">
                    <AudioPlayer audioUrl={audioData.url} mimeType={audioData.mimeType} />

                    <div className="flex items-center justify-between gap-4">
                        <TranscribeButton
                            onClick={handleTranscribeClick}
                            isModelLoading={transcriber.isModelLoading}
                            isTranscribing={transcriber.isBusy}
                        />

                        <button
                            onClick={resetAudio}
                            className="px-4 py-2 text-red-500 hover:text-red-600 transition-colors"
                        >
                            取消
                        </button>
                    </div>

                    <button
                        onClick={handleExportAudio}
                        className="w-full px-6 py-3 bg-green-500 hover:bg-green-600 text-white rounded-xl shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all text-lg font-semibold flex items-center justify-center gap-3"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        导出音频
                    </button>

                    {transcriber.isModelLoading && (
                        <div className="space-y-2">
                            <label className="text-sm text-slate-600">
                                正在上传并转录音频，请稍候...
                            </label>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                                <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{ width: '100%' }} />
                            </div>
                        </div>
                    )}
                </div>
            )}

            {Object.keys(transcribingSegments).length > 0 && (
                <div className="space-y-2">
                    <label className="text-sm text-slate-600">
                        自动转录进度: {Object.keys(transcribingSegments).length} 个片段处理中
                    </label>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                        <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{ width: '100%' }} />
                    </div>
                    <div className="flex flex-wrap gap-2">
                        {Object.entries(transcribingSegments).map(([index, status]) => (
                            <span key={index} className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded">
                                片段 {Number(index) + 1}: {status === 'uploading' ? '上传中' : '转录中'}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            <Modal
                show={showUrlModal}
                title="从链接添加音频"
                content={
                    <>
                        <p className="mb-4">输入要转录的音频文件链接。</p>
                        <UrlInput
                            onChange={(e) => setAudioDownloadUrl(e.target.value)}
                            value={audioDownloadUrl || Constants.DEFAULT_AUDIO_URL}
                        />
                    </>
                }
                onClose={() => setShowUrlModal(false)}
                submitText="加载音频"
                onSubmit={() => {}}
            />

            <Modal
                show={showRecordModal}
                title="录制音频"
                content={
                    <AudioRecorder
                        onRecordingComplete={setAudioFromRecording}
                        onSegmentAvailable={handleSegmentAvailable}
                        segmentInterval={30000}
                    />
                }
                onClose={() => setShowRecordModal(false)}
                onSubmit={() => {}}
            />
        </div>
    );
}
