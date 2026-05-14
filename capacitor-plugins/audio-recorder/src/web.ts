import { WebPlugin } from '@capacitor/core';
import type {
  AudioRecorderPlugin,
  SegmentInfo,
  StartRecordingOptions,
} from './definitions';

export class AudioRecorderWeb
  extends WebPlugin
  implements AudioRecorderPlugin
{
  private mediaRecorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private segmentTimeout: number | null = null;
  private segmentIndex = 0;
  private isRecording = false;
  private segments: SegmentInfo[] = [];

  async startRecording(options: StartRecordingOptions): Promise<void> {
    if (this.isRecording) {
      throw new Error('Recording already in progress');
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      this.isRecording = true;
      this.segmentIndex = 0;
      this.segments = [];
      this.startNextSegment(options.segmentInterval);
    } catch (error) {
      this.notifyListeners('recordingError', {
        message: error instanceof Error ? error.message : 'Failed to start recording',
      });
      throw error;
    }
  }

  async stopRecording(): Promise<{ filePath?: string; segments: SegmentInfo[] }> {
    this.isRecording = false;
    if (this.segmentTimeout) {
      clearTimeout(this.segmentTimeout);
      this.segmentTimeout = null;
    }
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
    const result = { segments: [...this.segments] };
    this.segments = [];
    return result;
  }

  async getSegments(): Promise<{ segments: SegmentInfo[] }> {
    return { segments: [...this.segments] };
  }

  private startNextSegment(interval: number): void {
    if (!this.isRecording || !this.stream) return;

    const mimeType = this.getSupportedMimeType();
    this.mediaRecorder = new MediaRecorder(this.stream, {
      mimeType,
      audioBitsPerSecond: 64000,
    });

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        const url = URL.createObjectURL(event.data);
        const segment: SegmentInfo = {
          index: this.segmentIndex,
          filePath: url,
          duration: interval / 1000,
          size: event.data.size,
        };
        this.segments.push(segment);
        this.notifyListeners('segmentAvailable', segment);
      }
    };

    this.mediaRecorder.start();

    this.segmentTimeout = window.setTimeout(() => {
      if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
        this.mediaRecorder.stop();
        this.segmentIndex++;
        this.startNextSegment(interval);
      }
    }, interval);
  }

  private getSupportedMimeType(): string {
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
}
