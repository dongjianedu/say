# 格调9问 - 移动端 App

基于 Capacitor 封装的跨平台移动应用，支持 iOS 和 Android。

## 特性

- 锁屏/后台持续录音
- 30 秒自动分段转录
- 原生音频处理，不受浏览器限制
- Web 代码 90%+ 复用

## 环境要求

### 通用
- Node.js >= 18
- npm >= 9

### iOS
- macOS >= 13
- Xcode >= 15
- CocoaPods (自动安装)

### Android
- Android Studio >= 2023
- JDK >= 17
- Android SDK >= 34

## 开发流程

### 1. 安装依赖
```bash
npm install
```

### 2. 开发模式（Web）
```bash
npm run dev
```

### 3. 构建并同步到原生项目
```bash
npm run native:build
```

### 4. 打开原生 IDE

**iOS:**
```bash
npm run cap:open:ios
```

**Android:**
```bash
npm run cap:open:android
```

### 5. 在 IDE 中运行/调试
- iOS: 在 Xcode 中选择模拟器或真机，点击 Run
- Android: 在 Android Studio 中选择模拟器或真机，点击 Run

## 项目结构

```
├── src/                          # React Web 源码
│   ├── components/
│   │   └── AudioRecorder.tsx     # 录音组件（自动切换原生/Web）
│   └── ...
├── capacitor-plugins/            # 自定义 Capacitor 插件
│   └── audio-recorder/
│       ├── src/
│       │   ├── definitions.ts    # TypeScript 接口
│       │   ├── web.ts            # Web 回退实现
│       │   └── index.ts          # 插件导出
│       ├── ios/                  # iOS 原生实现
│       │   └── Sources/AudioRecorderPlugin/
│       │       └── AudioRecorderPlugin.swift
│       └── android/              # Android 原生实现
│           └── src/main/java/...
│               └── AudioRecorderPlugin.kt
├── ios/                          # iOS 原生项目（git ignore）
├── android/                      # Android 原生项目（git ignore）
├── capacitor.config.json         # Capacitor 配置
└── package.json
```

## 原生插件说明

### AudioRecorder 插件

**接口定义:**
```typescript
interface AudioRecorderPlugin {
  startRecording(options: { segmentInterval: number }): Promise<void>;
  stopRecording(): Promise<{ segments: SegmentInfo[] }>;
  getSegments(): Promise<{ segments: SegmentInfo[] }>;
  addListener(eventName: 'segmentAvailable', listener: (segment) => void): Promise<PluginListenerHandle>;
  addListener(eventName: 'recordingError', listener: (error) => void): Promise<PluginListenerHandle>;
}
```

**iOS 实现要点:**
- 使用 `AVAudioRecorder` + `AVAudioSession`
- 配置 `UIBackgroundModes` 为 `audio`
- 每 30 秒自动分段保存到临时目录
- 通过 `NotificationCenter` 通知前端

**Android 实现要点:**
- 使用 `MediaRecorder` + Foreground Service
- 配置 `RECORD_AUDIO` 和 `FOREGROUND_SERVICE` 权限
- 前台服务显示持久通知，防止被系统杀死
- 每 30 秒分段保存到缓存目录

## 常见问题

### Q: 锁屏后录音中断？
A: 确保已正确配置后台音频权限：
- iOS: `Info.plist` 中 `UIBackgroundModes` 包含 `audio`
- Android: 已添加 `FOREGROUND_SERVICE` 权限

### Q: 如何调试原生代码？
A: 
- iOS: 在 Xcode 中设置断点，使用 Console 查看日志
- Android: 在 Android Studio 中使用 Logcat 查看日志

### Q: Web 端如何测试？
A: 运行 `npm run dev`，插件会自动使用 Web 回退实现（`MediaRecorder`）。

## 发布

### iOS
1. 在 Xcode 中配置签名证书
2. Product > Archive
3. 通过 TestFlight 或 App Store Connect 发布

### Android
1. 在 Android Studio 中配置签名
2. Build > Generate Signed Bundle / APK
3. 通过 Google Play Console 发布
