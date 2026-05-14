import Foundation
import AVFoundation
import Capacitor

@objc(AudioRecorderPlugin)
public class AudioRecorderPlugin: CAPPlugin {
    private var audioRecorder: AVAudioRecorder?
    private var audioSession: AVAudioSession?
    private var segmentTimer: Timer?
    private var segmentIndex = 0
    private var isRecording = false
    private var segmentInterval: TimeInterval = 30.0
    private var tempDirectory: URL?
    private var segments: [[String: Any]] = []

    @objc func startRecording(_ call: CAPPluginCall) {
        if isRecording {
            call.reject("Recording already in progress")
            return
        }

        segmentInterval = call.getDouble("segmentInterval") ?? 30000.0 / 1000.0
        segmentIndex = 0
        segments = []
        tempDirectory = FileManager.default.temporaryDirectory

        audioSession = AVAudioSession.sharedInstance()

        do {
            try audioSession?.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetooth])
            try audioSession?.setActive(true)
        } catch {
            call.reject("Failed to configure audio session: \(error.localizedDescription)")
            return
        }

        let recordingUrl = tempDirectory!.appendingPathComponent("segment_\(segmentIndex).m4a")

        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16000.0,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue
        ]

        do {
            audioRecorder = try AVAudioRecorder(url: recordingUrl, settings: settings)
            audioRecorder?.delegate = self
            audioRecorder?.record()
            isRecording = true

            segmentTimer = Timer.scheduledTimer(
                withTimeInterval: segmentInterval,
                repeats: false
            ) { [weak self] _ in
                self?.rotateSegment()
            }

            call.resolve()
        } catch {
            call.reject("Failed to start recording: \(error.localizedDescription)")
        }
    }

    @objc func stopRecording(_ call: CAPPluginCall) {
        if !isRecording {
            call.reject("Not recording")
            return
        }

        isRecording = false
        segmentTimer?.invalidate()
        segmentTimer = nil
        audioRecorder?.stop()

        do {
            try audioSession?.setActive(false)
        } catch {}

        let result: [String: Any] = [
            "segments": segments
        ]
        segments = []
        call.resolve(result)
    }

    @objc func getSegments(_ call: CAPPluginCall) {
        call.resolve(["segments": segments])
    }

    private func rotateSegment() {
        guard isRecording else { return }

        audioRecorder?.stop()

        if let currentUrl = audioRecorder?.url {
            let duration = audioRecorder?.currentTime ?? 0
            let fileSize = try? FileManager.default.attributesOfItem(atPath: currentUrl.path)[.size] as? Int64

            let segment: [String: Any] = [
                "index": segmentIndex,
                "filePath": currentUrl.path,
                "duration": duration,
                "size": fileSize ?? 0
            ]
            segments.append(segment)

            notifyListeners("segmentAvailable", data: segment)
        }

        segmentIndex += 1
        let newUrl = tempDirectory!.appendingPathComponent("segment_\(segmentIndex).m4a")

        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16000.0,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue
        ]

        do {
            audioRecorder = try AVAudioRecorder(url: newUrl, settings: settings)
            audioRecorder?.delegate = self
            audioRecorder?.record()

            segmentTimer = Timer.scheduledTimer(
                withTimeInterval: segmentInterval,
                repeats: false
            ) { [weak self] _ in
                self?.rotateSegment()
            }
        } catch {
            notifyListeners("recordingError", data: ["message": "Failed to create new segment: \(error.localizedDescription)"])
        }
    }
}

extension AudioRecorderPlugin: AVAudioRecorderDelegate {
    public func audioRecorderDidFinishRecording(_ recorder: AVAudioRecorder, successfully flag: Bool) {
        if flag && isRecording {
            rotateSegment()
        }
    }

    public func audioRecorderEncodeErrorDidOccur(_ recorder: AVAudioRecorder, error: Error?) {
        if let error = error {
            notifyListeners("recordingError", data: ["message": "Encoding error: \(error.localizedDescription)"])
        }
    }
}
