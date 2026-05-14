package com.gediao9.app;

import android.Manifest;
import android.content.Intent;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;

import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

import org.json.JSONArray;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

@CapacitorPlugin(
    name = "AudioRecorder",
    permissions = {
        @Permission(alias = "microphone", strings = { Manifest.permission.RECORD_AUDIO })
    }
)
public class AudioRecorderPlugin extends Plugin {
    private MediaRecorder mediaRecorder;
    private Handler segmentHandler;
    private Runnable segmentRunnable;
    private final List<JSObject> segments = new ArrayList<>();
    private boolean isRecording = false;
    private long segmentInterval = 30000L;
    private int currentSegmentIndex = 0;
    private long currentSegmentStartTime = 0L;
    private File currentSegmentFile;

    @PluginMethod
    public void startRecording(PluginCall call) {
        if (getPermissionState("microphone") != PermissionState.GRANTED) {
            requestPermissionForAlias("microphone", call, "startRecordingAfterPermission");
            return;
        }

        startRecordingInternal(call);
    }

    @PermissionCallback
    private void startRecordingAfterPermission(PluginCall call) {
        if (getPermissionState("microphone") == PermissionState.GRANTED) {
            startRecordingInternal(call);
        } else {
            call.reject("Microphone permission denied");
        }
    }

    private void startRecordingInternal(PluginCall call) {
        if (isRecording) {
            cleanupState();
            call.reject("Recording already in progress");
            return;
        }

        cleanupState();

        Long interval = call.getLong("segmentInterval", 30000L);
        segmentInterval = interval == null ? 30000L : interval;
        currentSegmentIndex = 0;
        segments.clear();
        segmentHandler = new Handler(Looper.getMainLooper());
        isRecording = true;

        Intent serviceIntent = new Intent(getContext(), RecordingForegroundService.class);
        serviceIntent.setAction(RecordingForegroundService.ACTION_START);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getContext().startForegroundService(serviceIntent);
        } else {
            getContext().startService(serviceIntent);
        }

        try {
            startCurrentSegment();
            call.resolve();
        } catch (Exception error) {
            isRecording = false;
            cleanupState();
            stopForegroundService();
            notifyError("Failed to start recording: " + error.getMessage());
            call.reject("Failed to start recording: " + error.getMessage());
        }
    }

    @PluginMethod
    public void stopRecording(PluginCall call) {
        if (!isRecording) {
            call.reject("Not recording");
            return;
        }

        isRecording = false;

        if (segmentHandler != null) {
            segmentHandler.removeCallbacksAndMessages(null);
            segmentHandler = null;
        }
        segmentRunnable = null;

        stopCurrentSegment(true);
        stopForegroundService();

        JSObject result = new JSObject();
        JSONArray segmentArray = new JSONArray();
        for (JSObject segment : segments) {
            segmentArray.put(segment);
        }
        result.put("segments", segmentArray);
        segments.clear();
        call.resolve(result);
    }

    @PluginMethod
    public void getSegments(PluginCall call) {
        JSObject result = new JSObject();
        JSONArray segmentArray = new JSONArray();
        for (JSObject segment : segments) {
            segmentArray.put(segment);
        }
        result.put("segments", segmentArray);
        call.resolve(result);
    }

    private void startCurrentSegment() throws Exception {
        currentSegmentFile = new File(
            getContext().getCacheDir(),
            "segment_" + System.currentTimeMillis() + "_" + currentSegmentIndex + ".m4a"
        );

        mediaRecorder = createRecorder();
        mediaRecorder.setAudioSource(MediaRecorder.AudioSource.MIC);
        mediaRecorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
        mediaRecorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
        mediaRecorder.setAudioSamplingRate(16000);
        mediaRecorder.setAudioEncodingBitRate(64000);
        mediaRecorder.setAudioChannels(1);
        mediaRecorder.setOutputFile(currentSegmentFile.getAbsolutePath());
        mediaRecorder.prepare();
        mediaRecorder.start();
        currentSegmentStartTime = System.currentTimeMillis();

        segmentRunnable = () -> {
            if (!isRecording) return;
            rotateSegment();
        };
        segmentHandler.postDelayed(segmentRunnable, segmentInterval);
    }

    private MediaRecorder createRecorder() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return new MediaRecorder(getContext());
        }

        return new MediaRecorder();
    }

    private void rotateSegment() {
        stopCurrentSegment(true);
        currentSegmentIndex += 1;

        if (!isRecording) return;

        try {
            startCurrentSegment();
        } catch (Exception error) {
            isRecording = false;
            if (segmentHandler != null) {
                segmentHandler.removeCallbacksAndMessages(null);
                segmentHandler = null;
            }
            segmentRunnable = null;
            stopForegroundService();
            notifyError("Failed to rotate recording segment: " + error.getMessage());
        }
    }

    private void stopCurrentSegment(boolean emitSegment) {
        if (mediaRecorder != null) {
            try {
                mediaRecorder.stop();
            } catch (RuntimeException ignored) {
                // Android throws if a segment is too short or contains no audio data.
            }
            mediaRecorder.release();
            mediaRecorder = null;
        }

        if (!emitSegment || currentSegmentFile == null || !currentSegmentFile.exists() || currentSegmentFile.length() == 0) {
            return;
        }

        double duration = (System.currentTimeMillis() - currentSegmentStartTime) / 1000.0;
        JSObject segment = new JSObject();
        segment.put("index", currentSegmentIndex);
        segment.put("filePath", currentSegmentFile.getName());
        segment.put("duration", duration);
        segment.put("size", currentSegmentFile.length());
        segments.add(segment);
        notifyListeners("segmentAvailable", segment);
    }

    private void notifyError(String message) {
        JSObject error = new JSObject();
        error.put("message", message);
        notifyListeners("recordingError", error);
    }

    private void cleanupState() {
        if (mediaRecorder != null) {
            try {
                mediaRecorder.stop();
            } catch (RuntimeException ignored) {
            }
            mediaRecorder.release();
            mediaRecorder = null;
        }

        if (segmentHandler != null) {
            segmentHandler.removeCallbacksAndMessages(null);
            segmentHandler = null;
        }
        segmentRunnable = null;
        isRecording = false;
    }

    private void stopForegroundService() {
        Intent serviceIntent = new Intent(getContext(), RecordingForegroundService.class);
        serviceIntent.setAction(RecordingForegroundService.ACTION_STOP);
        getContext().startService(serviceIntent);
    }
}
