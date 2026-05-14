import type { PluginListenerHandle } from '@capacitor/core';

export interface SegmentInfo {
  index: number;
  filePath: string;
  duration: number;
  size: number;
}

export interface StartRecordingOptions {
  segmentInterval: number;
}

export interface AudioRecorderPlugin {
  startRecording(options: StartRecordingOptions): Promise<void>;
  stopRecording(): Promise<{ filePath?: string; segments: SegmentInfo[] }>;
  getSegments(): Promise<{ segments: SegmentInfo[] }>;
  addListener(
    eventName: 'segmentAvailable',
    listenerFunc: (segment: SegmentInfo) => void
  ): Promise<PluginListenerHandle>;
  addListener(
    eventName: 'recordingError',
    listenerFunc: (error: { message: string }) => void
  ): Promise<PluginListenerHandle>;
}
