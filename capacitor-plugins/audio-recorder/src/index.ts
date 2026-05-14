import { registerPlugin } from '@capacitor/core';
import type { AudioRecorderPlugin } from './definitions';

const AudioRecorder = registerPlugin<AudioRecorderPlugin>('AudioRecorder', {
  web: () => import('./web').then((m) => new m.AudioRecorderWeb()),
});

export * from './definitions';
export { AudioRecorder };
