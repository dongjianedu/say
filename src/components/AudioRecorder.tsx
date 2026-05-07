import React, { useState, useRef } from 'react';
import { LiveAudioVisualizer } from 'react-audio-visualize';

interface Props {
  onRecordingComplete: (blob: Blob) => void;
  onSegmentAvailable?: (blob: Blob, index: number) => void;
  segmentInterval?: number;
}

function getSupportedMimeType(): string {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/ogg',
  ];

  for (const type of types) {
    if (MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }

  return 'audio/webm';
}

const AudioRecorder: React.FC<Props> = ({
  onRecordingComplete,
  onSegmentAvailable,
  segmentInterval = 30000,
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const timeInterval = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const segmentIndexRef = useRef(0);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      streamRef.current = stream;
      const mimeType = getSupportedMimeType();
      const recorder = new MediaRecorder(stream, {
        mimeType,
        audioBitsPerSecond: 64000,
      });

      segmentIndexRef.current = 0;

      recorder.addEventListener('dataavailable', (event) => {
        if (event.data.size > 0) {
          const currentIndex = segmentIndexRef.current++;
          onSegmentAvailable?.(event.data, currentIndex);
        }
      });

      recorder.addEventListener('stop', () => {
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
        }
      });

      recorder.start(segmentInterval);

      setMediaRecorder(recorder);
      setIsRecording(true);

      timeInterval.current = window.setInterval(() => {
        setRecordingTime((prevTime) => prevTime + 1);
      }, 1000);
    } catch (err) {
      console.error('Error accessing microphone:', err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      setIsRecording(false);
      if (timeInterval.current) {
        clearInterval(timeInterval.current);
        timeInterval.current = null;
      }
      setRecordingTime(0);
      setMediaRecorder(null);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex flex-col items-center gap-4 p-6 w-full max-w-2xl mx-auto">
      <div className="w-full bg-white rounded-lg p-6 shadow-lg">
        <h2 className="text-2xl font-bold mb-4">录制音频</h2>
        <div className="relative w-full">
          {mediaRecorder ? (
            <div className="w-full h-40 rounded-lg mb-4 bg-[rgb(15,23,42)] flex items-center justify-center overflow-hidden">
              <LiveAudioVisualizer
                mediaRecorder={mediaRecorder}
                width={800}
                height={160}
                barWidth={2}
                gap={1}
                barColor={'rgb(96, 165, 250)'}
                backgroundColor={'rgb(15, 23, 42)'}
                fftSize={1024}
                smoothingTimeConstant={0.8}
              />
            </div>
          ) : (
            <div
              className="w-full h-40 rounded-lg mb-4 bg-[rgb(15,23,42)] flex items-center justify-center"
            >
              <span className="text-white/50">
                点击"开始录音"按钮开始
              </span>
            </div>
          )}
        </div>
        <div className="text-center mb-4">
          <div className="text-xl font-semibold text-gray-700">
            {isRecording ? `录音中：${formatTime(recordingTime)}` : '准备就绪'}
          </div>
          {isRecording && (
            <div className="text-sm text-blue-500 mt-1">
              每30秒自动转录一次
            </div>
          )}
        </div>
        <button
          onClick={isRecording ? stopRecording : startRecording}
          className={`w-full py-3 rounded-lg text-white text-lg font-semibold ${
            isRecording
              ? 'bg-red-500 hover:bg-red-600'
              : 'bg-blue-500 hover:bg-blue-600'
          } transition-all shadow-md hover:shadow-lg`}
          aria-label={isRecording ? "停止录音" : "开始录音"}
        >
          {isRecording ? '停止录音' : '开始录音'}
        </button>
      </div>
    </div>
  );
};

export default AudioRecorder;
