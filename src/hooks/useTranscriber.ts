import { useCallback, useMemo, useState } from "react";
import Constants from "../utils/Constants";
import type { ProgressItem } from "../types/model";


interface TranscriberCompleteData {
    text: string;
    chunks: { text: string; start_time: number; end_time: number; language: string }[];
    language: string;
}

export interface TranscriberData {
    isBusy: boolean;
    text: string;
    chunks: { text: string; timestamp: [number, number | null] }[];
    ossUrl?: string;
}

export interface Transcriber {
    onInputChange: () => void;
    isBusy: boolean;
    isModelLoading: boolean;
    progressItems: ProgressItem[];
    start: (audioBlob: Blob | undefined) => void;
    output?: TranscriberData;
    model: string;
    setModel: (model: string) => void;
    multilingual: boolean;
    setMultilingual: (model: boolean) => void;
    quantized: boolean;
    setQuantized: (model: boolean) => void;
    subtask: string;
    setSubtask: (subtask: string) => void;
    language?: string;
    setLanguage: (language: string) => void;
}

export function useTranscriber(): Transcriber {
    const [transcript, setTranscript] = useState<TranscriberData | undefined>(
        undefined,
    );
    const [isBusy, setIsBusy] = useState(false);
    const [isModelLoading, setIsModelLoading] = useState(false);
    const [progressItems, setProgressItems] = useState<ProgressItem[]>([]);

    const [model, setModel] = useState<string>(Constants.DEFAULT_MODEL);
    const [subtask, setSubtask] = useState<string>(Constants.DEFAULT_SUBTASK);
    const [quantized, setQuantized] = useState<boolean>(
        Constants.DEFAULT_QUANTIZED,
    );
    const [multilingual, setMultilingual] = useState<boolean>(
        Constants.DEFAULT_MULTILINGUAL,
    );
    const [language, setLanguage] = useState<string>(
        Constants.DEFAULT_LANGUAGE,
    );

    const onInputChange = useCallback(() => {
        setTranscript(undefined);
    }, []);

    const postRequest = useCallback(
        async (audioBlob: Blob | undefined) => {
            if (audioBlob) {
                setTranscript(undefined);
                setIsBusy(true);
                setIsModelLoading(true);

                let ossUrl: string | undefined;

                try {
                    const uploadFormData = new FormData();
                    uploadFormData.append('file', audioBlob, 'recording.webm');

                    const uploadResponse = await fetch(Constants.UPLOAD_API_URL, {
                        method: 'POST',
                        body: uploadFormData,
                    });

                    if (!uploadResponse.ok) {
                        throw new Error(`Upload failed! status: ${uploadResponse.status}`);
                    }

                    const uploadResult = await uploadResponse.json();
                    ossUrl = uploadResult.url;
                    console.log('Audio uploaded to OSS:', ossUrl);

                    const transcribeFormData = new FormData();
                    transcribeFormData.append('audio', audioBlob, 'recording.webm');

                    const response = await fetch(Constants.TRANSCRIBE_API_URL, {
                        method: 'POST',
                        body: transcribeFormData,
                    });

                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }

                    const result: TranscriberCompleteData = await response.json();

                    setTranscript({
                        isBusy: false,
                        text: result.text,
                        chunks: result.chunks.map(chunk => ({
                            text: chunk.text,
                            timestamp: [chunk.start_time / 1000, chunk.end_time / 1000] as [number, number],
                        })),
                        ossUrl,
                    });
                } catch (error) {
                    console.error('Transcription error:', error);
                    alert(`转录失败: ${error instanceof Error ? error.message : '未知错误'}`);
                    setTranscript(undefined);
                } finally {
                    setIsBusy(false);
                    setIsModelLoading(false);
                }
            }
        },
        [],
    );

    const transcriber = useMemo(() => {
        return {
            onInputChange,
            isBusy,
            isModelLoading,
            progressItems,
            start: postRequest,
            output: transcript,
            model,
            setModel,
            multilingual,
            setMultilingual,
            quantized,
            setQuantized,
            subtask,
            setSubtask,
            language,
            setLanguage,
        };
    }, [
        isBusy,
        isModelLoading,
        progressItems,
        postRequest,
        transcript,
        model,
        multilingual,
        quantized,
        subtask,
        language,
    ]);

    return transcriber;
}
