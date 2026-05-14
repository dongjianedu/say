package com.gediao9.audiorecorder

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.PackageManager
import android.media.MediaRecorder
import android.os.Build
import android.os.Handler
import android.os.Looper
import com.getcapacitor.JSObject
import com.getcapacitor.PermissionState
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import com.getcapacitor.annotation.Permission
import java.io.File
import java.io.IOException

@CapacitorPlugin(
    name = "AudioRecorder",
    permissions = [
        Permission(
            alias = "microphone",
            strings = [Manifest.permission.RECORD_AUDIO]
        )
    ]
)
class AudioRecorderPlugin : Plugin() {

    private var mediaRecorder: MediaRecorder? = null
    private var segmentHandler: Handler? = null
    private var segmentRunnable: Runnable? = null
    private var segmentIndex = 0
    private var isRecording = false
    private var segmentInterval: Long = 30000
    private var tempDir: File? = null
    private var segments = mutableListOf<Map<String, Any>>()
    private var startTime: Long = 0

    companion object {
        private const val NOTIFICATION_CHANNEL_ID = "audio_recorder_channel"
        private const val NOTIFICATION_ID = 1
    }

    @PluginMethod
    fun startRecording(call: PluginCall) {
        if (getPermissionState("microphone") != PermissionState.GRANTED) {
            requestPermissionForAlias("microphone", call, "startRecordingAfterPermission")
            return
        }
        executeStartRecording(call)
    }

    private fun startRecordingAfterPermission(call: PluginCall) {
        if (getPermissionState("microphone") == PermissionState.GRANTED) {
            executeStartRecording(call)
        } else {
            call.reject("Microphone permission denied")
        }
    }

    private fun executeStartRecording(call: PluginCall) {
        if (isRecording) {
            call.reject("Recording already in progress")
            return
        }

        segmentInterval = call.getLong("segmentInterval", 30000)
        segmentIndex = 0
        segments.clear()
        tempDir = context.cacheDir

        segmentHandler = Handler(Looper.getMainLooper())

        try {
            createNotificationChannel()
            startForegroundNotification()
            startNextSegment()
            call.resolve()
        } catch (e: Exception) {
            call.reject("Failed to start recording: ${e.message}")
        }
    }

    @PluginMethod
    fun stopRecording(call: PluginCall) {
        if (!isRecording) {
            call.reject("Not recording")
            return
        }

        isRecording = false
        segmentRunnable?.let { segmentHandler?.removeCallbacks(it) }
        mediaRecorder?.stop()
        mediaRecorder?.release()
        mediaRecorder = null
        stopForegroundNotification()

        val result = JSObject()
        val segmentsArray = JSObject()
        for ((i, segment) in segments.withIndex()) {
            val segObj = JSObject()
            segObj.put("index", segment["index"] as Int)
            segObj.put("filePath", segment["filePath"] as String)
            segObj.put("duration", segment["duration"] as Double)
            segObj.put("size", segment["size"] as Long)
            segmentsArray.put(i.toString(), segObj)
        }
        result.put("segments", segmentsArray)
        segments.clear()
        call.resolve(result)
    }

    @PluginMethod
    fun getSegments(call: PluginCall) {
        val result = JSObject()
        val segmentsArray = JSObject()
        for ((i, segment) in segments.withIndex()) {
            val segObj = JSObject()
            segObj.put("index", segment["index"] as Int)
            segObj.put("filePath", segment["filePath"] as String)
            segObj.put("duration", segment["duration"] as Double)
            segObj.put("size", segment["size"] as Long)
            segmentsArray.put(i.toString(), segObj)
        }
        result.put("segments", segmentsArray)
        call.resolve(result)
    }

    private fun startNextSegment() {
        if (!isRecording && segmentIndex > 0) return

        mediaRecorder?.stop()
        mediaRecorder?.release()

        val outputFile = File(tempDir, "segment_$segmentIndex.m4a")
        val duration = (System.currentTimeMillis() - startTime) / 1000.0
        val fileSize = outputFile.length()

        if (segmentIndex > 0 || isRecording) {
            val segment = mapOf(
                "index" to segmentIndex,
                "filePath" to outputFile.absolutePath,
                "duration" to duration,
                "size" to fileSize
            )
            segments.add(segment)

            val data = JSObject()
            data.put("index", segmentIndex)
            data.put("filePath", outputFile.absolutePath)
            data.put("duration", duration)
            data.put("size", fileSize)
            notifyListeners("segmentAvailable", data)
        }

        isRecording = true
        segmentIndex++

        mediaRecorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(context)
        } else {
            @Suppress("DEPRECATION")
            MediaRecorder()
        }.apply {
            setAudioSource(MediaRecorder.AudioSource.MIC)
            setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            setAudioSamplingRate(16000)
            setAudioChannels(1)
            setOutputFile(outputFile.absolutePath)
            try {
                prepare()
                start()
                startTime = System.currentTimeMillis()
            } catch (e: IOException) {
                val error = JSObject()
                error.put("message", "Failed to prepare recorder: ${e.message}")
                notifyListeners("recordingError", error)
                return
            }
        }

        segmentRunnable = Runnable {
            startNextSegment()
        }
        segmentHandler?.postDelayed(segmentRunnable!!, segmentInterval)
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "录音服务",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "保持录音在后台运行"
            }
            val manager = context.getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun startForegroundNotification() {
        val notification = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(context, NOTIFICATION_CHANNEL_ID)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(context)
        }.apply {
            setContentTitle("格调9问")
            setContentText("正在录音...")
            setSmallIcon(android.R.drawable.ic_btn_speak_now)
            setOngoing(true)
        }.build()

        // Note: In a real app, you'd need to use startForeground() from a Service
        // This is a simplified version
    }

    private fun stopForegroundNotification() {
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.cancel(NOTIFICATION_ID)
    }
}
