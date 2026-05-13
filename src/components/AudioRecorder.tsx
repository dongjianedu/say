import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Capacitor } from '@capacitor/core';
import type { PluginListenerHandle } from '@capacitor/core';
import { AudioRecorder } from '../../capacitor-plugins/audio-recorder/src';
import { Filesystem, Directory } from '@capacitor/filesystem';
import { LiveAudioVisualizer } from 'react-audio-visualize';

interface Props {
  onRecordingComplete: (blob: Blob) => void;
  onSegmentAvailable?: (blob: Blob, index: number) => void;
  onRecordingStart?: () => void;
  onRecordingStop?: () => void;
  segmentInterval?: number;
}

const isNative = Capacitor.isNativePlatform();

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

const AudioRecorderComponent: React.FC<Props> = ({
  onRecordingComplete,
  onSegmentAvailable,
  onRecordingStart,
  onRecordingStop,
  segmentInterval = 30000,
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);

  const timeInterval = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const activeRecorderRef = useRef<MediaRecorder | null>(null);
  const isRecordingRef = useRef(false);
  const segmentIndexRef = useRef(0);
  const segmentTimeoutRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const visualizerActiveRef = useRef(false);
  const nativeListenerRef = useRef<PluginListenerHandle | null>(null);

  const drawVisualizer = useCallback(() => {
    const canvas = canvasRef.current;
    const analyser = analyserRef.current;
    if (!canvas || !analyser) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      if (!visualizerActiveRef.current) return;
      animationFrameRef.current = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);

      ctx.fillStyle = 'rgb(15, 23, 42)';
      ctx.fillRect(0, 0, width, height);

      const barWidth = 2;
      const gap = 1;
      const totalBarWidth = barWidth + gap;
      const barCount = Math.floor(width / totalBarWidth);
      const step = Math.floor(bufferLength / barCount);

      for (let i = 0; i < barCount; i++) {
        const value = dataArray[i * step];
        const barHeight = (value / 255) * height;
        const x = i * totalBarWidth;
        const y = height - barHeight;

        ctx.fillStyle = `rgba(96, 165, 250, 0.8)`;
        ctx.fillRect(x, y, barWidth, barHeight);
      }
    };

    draw();
  }, []);

  const stopVisualizer = useCallback(() => {
    visualizerActiveRef.current = false;
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      stopVisualizer();
      if (timeInterval.current) clearInterval(timeInterval.current);
      if (segmentTimeoutRef.current) clearTimeout(segmentTimeoutRef.current);
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
      if (audioContextRef.current) audioContextRef.current.close();
      nativeListenerRef.current?.remove();
    };
  }, [stopVisualizer]);

  useEffect(() => {
    if (isRecording && canvasRef.current && analyserRef.current) {
      visualizerActiveRef.current = true;
      drawVisualizer();
    } else if (!isRecording) {
      stopVisualizer();
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.fillStyle = 'rgb(15, 23, 42)';
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.fillStyle = 'rgba(255, 255, 255, 0.5)';
          ctx.font = '16px sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText('点击"开始录音"按钮开始', canvas.width / 2, canvas.height / 2);
        }
      }
    }
  }, [isRecording, drawVisualizer, stopVisualizer]);

  const handleNativeSegment = useCallback(async (segment: { filePath: string; index: number }) => {
    try {
      const fileData = await Filesystem.readFile({
        path: segment.filePath,
        directory: Directory.Cache,
      });

      let blob: Blob;
      if (typeof fileData.data === 'string') {
        const byteCharacters = atob(fileData.data);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        blob = new Blob([byteArray], { type: 'audio/mp4' });
      } else {
        blob = new Blob([fileData.data], { type: 'audio/mp4' });
      }

      onSegmentAvailable?.(blob, segment.index);
    } catch (error) {
      console.error('Error reading native segment file:', error);
    }
  }, [onSegmentAvailable]);

  const startRecording = async () => {
    try {
      if (isNative) {
        nativeListenerRef.current = await AudioRecorder.addListener(
          'segmentAvailable',
          handleNativeSegment
        );
        await AudioRecorder.addListener(
          'recordingError',
          (error: { message: string }) => {
            console.error('Native recording error:', error.message);
            alert('录音出错: ' + error.message);
          }
        );
        await AudioRecorder.startRecording({ segmentInterval });
        setIsRecording(true);
        onRecordingStart?.();

        timeInterval.current = window.setInterval(() => {
          setRecordingTime(prev => prev + 1);
        }, 1000);
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      streamRef.current = stream;
      segmentIndexRef.current = 0;
      isRecordingRef.current = true;
      setIsRecording(true);
      onRecordingStart?.();

      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.8;
      source.connect(analyser);
      analyserRef.current = analyser;

      const startNextSegment = () => {
        if (!isRecordingRef.current || !streamRef.current) return;

        const mimeType = getSupportedMimeType();
        const recorder = new MediaRecorder(streamRef.current, {
          mimeType,
          audioBitsPerSecond: 64000,
        });
        activeRecorderRef.current = recorder;

        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            onSegmentAvailable?.(e.data, segmentIndexRef.current);
          }
        };

        recorder.onstop = () => {
          segmentIndexRef.current++;
          if (isRecordingRef.current && streamRef.current?.active) {
            startNextSegment();
          }
        };

        recorder.start();

        segmentTimeoutRef.current = window.setTimeout(() => {
          if (recorder.state === 'recording') {
            recorder.stop();
          }
        }, segmentInterval);
      };

      startNextSegment();

      timeInterval.current = window.setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } catch (err) {
      console.error('Error accessing microphone:', err);
    }
  };

  const stopRecording = async () => {
    if (isNative) {
      await AudioRecorder.stopRecording();
      nativeListenerRef.current?.remove();
      nativeListenerRef.current = null;
      setIsRecording(false);
      if (timeInterval.current) {
        clearInterval(timeInterval.current);
        timeInterval.current = null;
      }
      setRecordingTime(0);
      onRecordingStop?.();
      return;
    }

    isRecordingRef.current = false;
    if (activeRecorderRef.current && activeRecorderRef.current.state !== 'inactive') {
      activeRecorderRef.current.stop();
    }
    if (segmentTimeoutRef.current) clearTimeout(segmentTimeoutRef.current);
    setIsRecording(false);
    if (timeInterval.current) {
      clearInterval(timeInterval.current);
      timeInterval.current = null;
    }
    setRecordingTime(0);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    onRecordingStop?.();
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const nativeWaveformRef = useRef<HTMLDivElement>(null);
  const [waveformHeights, setWaveformHeights] = useState<number[]>([]);

  useEffect(() => {
    if (isRecording && isNative) {
      const barCount = 200;
      setWaveformHeights(Array(barCount).fill(10));
      const interval = setInterval(() => {
        setWaveformHeights(prev =>
          prev.map(() => Math.random() * 90 + 10)
        );
      }, 100);
      return () => clearInterval(interval);
    } else {
      setWaveformHeights([]);
    }
  }, [isRecording, isNative]);

  return (
    <div className="flex flex-col items-center gap-4 p-6 w-full max-w-2xl mx-auto">
      <div className="w-full bg-white rounded-lg p-6 shadow-lg">
        <h2 className="text-2xl font-bold mb-4">录制音频</h2>
        <div className="relative w-full">
          {isRecording && !isNative ? (
            <div className="w-full h-40 rounded-lg mb-4 bg-[rgb(15,23,42)] flex items-center justify-center overflow-hidden">
              <canvas
                ref={canvasRef}
                width={800}
                height={160}
                className="w-full h-full"
              />
            </div>
          ) : isRecording && isNative ? (
            <div className="w-full h-40 rounded-lg mb-4 bg-[rgb(15,23,42)] flex items-center justify-center overflow-hidden">
              <div className="flex items-center justify-center gap-[2px] h-full px-4">
                {waveformHeights.map((height, i) => (
                  <div
                    key={i}
                    className="w-[3px] rounded-full bg-blue-400 transition-all duration-100"
                    style={{ height: `${height}%`, opacity: 0.6 + (height / 250) }}
                  />
                ))}
              </div>
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
              {isNative ? '后台录音已启用' : '每30秒自动转录一次'}
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

export default AudioRecorderComponent;
