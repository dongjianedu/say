import { useState, useCallback, useRef } from 'react';
import Constants from '../utils/Constants';

interface TranscriptionTask {
    taskId: string;
    ossUrl: string;
    segmentIndex: number;
    status: 'pending' | 'uploading' | 'submitting' | 'polling' | 'succeeded' | 'failed';
    text?: string;
    error?: string;
}

interface Note {
    id: string;
    title: string;
    content: string;
    tags: string[];
    versions: any[];
    created: number;
    lastEdited: number;
    ossUrl?: string;
}

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_COUNT = 200;

export const useAutoTranscriber = (onNoteCreated: (note: Note) => void) => {
    const [tasks, setTasks] = useState<Map<string, TranscriptionTask>>(new Map());
    const abortRefs = useRef<Map<string, boolean>>(new Map());

    const uploadToOss = useCallback(async (blob: Blob, segmentIndex: number): Promise<string> => {
        const formData = new FormData();
        formData.append('file', blob, `segment-${segmentIndex}.webm`);

        const response = await fetch(Constants.UPLOAD_API_URL, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`Upload failed! status: ${response.status}`);
        }

        const result = await response.json();
        return result.url;
    }, []);

    const submitAsyncTranscription = useCallback(async (audioUrl: string): Promise<string> => {
        const response = await fetch(Constants.TRANSCRIBE_ASYNC_API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ audio_url: audioUrl }),
        });

        if (!response.ok) {
            throw new Error(`Submit async task failed! status: ${response.status}`);
        }

        const result = await response.json();
        return result.task_id;
    }, []);

    const pollTranscriptionStatus = useCallback(async (
        taskId: string,
        ossUrl: string,
        segmentIndex: number
    ) => {
        abortRefs.current.set(taskId, false);
        let pollCount = 0;

        while (pollCount < MAX_POLL_COUNT) {
            if (abortRefs.current.get(taskId)) {
                console.log(`Polling aborted for task ${taskId}`);
                return;
            }

            await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));

            try {
                const statusRes = await fetch(`${Constants.TRANSCRIBE_STATUS_API_URL}/${taskId}`);
                const statusData = await statusRes.json();

                if (statusData.status === 'SUCCEEDED') {
                    const result = statusData.result;
                    const note: Note = {
                        id: `${Date.now()}-${segmentIndex}`,
                        title: `转录片段 ${segmentIndex + 1}`,
                        content: result.text || '',
                        tags: [],
                        versions: [],
                        created: Date.now(),
                        lastEdited: Date.now(),
                        ossUrl,
                    };

                    setTasks(prev => {
                        const next = new Map(prev);
                        const task = next.get(taskId);
                        if (task) {
                            next.set(taskId, { ...task, status: 'succeeded', text: result.text });
                        }
                        return next;
                    });

                    onNoteCreated(note);
                    return;
                } else if (statusData.status === 'FAILED') {
                    throw new Error(statusData.message || 'Transcription failed');
                }
            } catch (error) {
                console.error(`Poll error for task ${taskId}:`, error);
                if (pollCount >= 3) {
                    setTasks(prev => {
                        const next = new Map(prev);
                        const task = next.get(taskId);
                        if (task) {
                            next.set(taskId, {
                                ...task,
                                status: 'failed',
                                error: error instanceof Error ? error.message : 'Unknown error'
                            });
                        }
                        return next;
                    });
                    return;
                }
            }

            pollCount++;
        }

        setTasks(prev => {
            const next = new Map(prev);
            const task = next.get(taskId);
            if (task) {
                next.set(taskId, { ...task, status: 'failed', error: 'Transcription timed out' });
            }
            return next;
        });
    }, [onNoteCreated]);

    const processAudioSegment = useCallback(async (blob: Blob, segmentIndex: number) => {
        const taskId = `segment-${segmentIndex}-${Date.now()}`;

        setTasks(prev => {
            const next = new Map(prev);
            next.set(taskId, {
                taskId,
                ossUrl: '',
                segmentIndex,
                status: 'uploading',
            });
            return next;
        });

        try {
            const ossUrl = await uploadToOss(blob, segmentIndex);

            setTasks(prev => {
                const next = new Map(prev);
                const task = next.get(taskId);
                if (task) {
                    next.set(taskId, { ...task, ossUrl, status: 'submitting' });
                }
                return next;
            });

            const newTaskId = await submitAsyncTranscription(ossUrl);

            setTasks(prev => {
                const next = new Map(prev);
                next.delete(taskId);
                next.set(newTaskId, {
                    taskId: newTaskId,
                    ossUrl,
                    segmentIndex,
                    status: 'polling',
                });
                return next;
            });

            pollTranscriptionStatus(newTaskId, ossUrl, segmentIndex);
        } catch (error) {
            console.error(`Error processing segment ${segmentIndex}:`, error);
            setTasks(prev => {
                const next = new Map(prev);
                const task = next.get(taskId);
                if (task) {
                    next.set(taskId, {
                        ...task,
                        status: 'failed',
                        error: error instanceof Error ? error.message : 'Unknown error'
                    });
                }
                return next;
            });
        }
    }, [uploadToOss, submitAsyncTranscription, pollTranscriptionStatus]);

    const cleanup = useCallback(() => {
        abortRefs.current.forEach((_, taskId) => {
            abortRefs.current.set(taskId, true);
        });
    }, []);

    return {
        tasks,
        processAudioSegment,
        cleanup,
    };
};
