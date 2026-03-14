import { useState, useEffect, useRef } from 'react'
import io, { Socket } from 'socket.io-client'
import { TitleBar } from './components/TitleBar'
import { HeaderStrip } from './components/hud/HeaderStrip'
import { TelemetryPanel } from './components/hud/TelemetryPanel'
import { VoiceCorePanel } from './components/hud/VoiceCorePanel'
import { LogsPanel } from './components/hud/LogsPanel'
import './App.css'

interface TelemetryData {
  cpu: {
    result: any;
    stats: {
      physical_cores: number;
      logical_cores: number;
      avg_usage_percentage: number;
      high_usage_alert: boolean;
    };
    additional_info: any;
  };
  memory: {
    result: any;
    stats: {
      memory_usage_percentage: number;
      swap_usage_percentage: number;
      total_memory_gb: number;
      available_memory_gb: number;
    };
    additional_info: any;
  };
  disk: {
    result: any;
    stats: {
      partition_count: number;
      total_space_gb: number;
      used_space_gb: number;
      overall_usage_percent: number;
      partitions_with_high_usage: number;
    };
    additional_info: any;
  };
  gpu?: {
    nvidia: {
      name: string;
      type: string;
      usage_percentage: number;
      memory_usage_percentage: number;
      memory_used_mb: number;
      memory_total_mb: number;
      temperature: number;
    } | null;
    intel: {
      name: string;
      type: string;
      usage_percentage: number;
    } | null;
    stats: {
      avg_usage_percentage: number;
      memory_usage_percentage: number;
      temperature: number;
    };
  };
  network?: {
    stats: {
      upload_mbps: number;
      download_mbps: number;
    };
  };
  battery?: {
    stats: {
      percent: number;
      power_plugged: boolean;
    };
  };
}


interface LogMessage {
  id: string
  timestamp: string
  message: string
}

type LogType = 'user' | 'vega' | 'scene' | 'warning' | 'error' | 'system'

function App() {
  const [isListening, setIsListening] = useState(false)
  const [systemState, setSystemState] = useState<'IDLE' | 'LISTENING' | 'PROCESSING' | 'SPEAKING'>('IDLE')
  const [socketStatus, setSocketStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting')
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null)
  const [currentScene, setCurrentScene] = useState<{ mode: string; color: string }>({ mode: 'IDLE', color: '#64748b' })
  const [logs, setLogs] = useState<LogMessage[]>([])
  const [inputText, setInputText] = useState('')
  const [micActive, setMicActive] = useState(false)
  const [wakeFlash, setWakeFlash] = useState(false)
  const [visionEnabled, setVisionEnabled] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const socketRef = useRef<Socket | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const microphoneRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const requestRef = useRef<number | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<BlobPart[]>([])
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isSpeakingRef = useRef<boolean>(false)
  const stopListeningRef = useRef<() => void>(() => { })
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const currentSourceRef = useRef<AudioBufferSourceNode | null>(null)
  const wasListeningBeforeSpeakRef = useRef<boolean>(false)

  // Audio Queue System
  const audioQueueRef = useRef<{ audio: string, format: string, sampleRate?: number, silent?: boolean }[]>([])
  const isAudioPlayingRef = useRef<boolean>(false)
  const playbackContextRef = useRef<AudioContext | null>(null)

  useEffect(() => {
    const socket = io('http://127.0.0.1:8000')
    socketRef.current = socket

    socket.on('connect', () => {
      setSocketStatus('connected')
      addLog('System connected to backend server.')
    })

    socket.on('disconnect', () => {
      setSocketStatus('disconnected')
      addLog('System disconnected. Reconnecting...')
    })

    socket.on('telemetry', (data: TelemetryData) => {
      setTelemetry(data)
      if ((window as any).ipcRenderer) {
        (window as any).ipcRenderer.send('splash-telemetry', data)
      }
    })

    const handleFastTelemetry = (_event: any, fastData: Partial<TelemetryData>) => {
      setTelemetry(prev => {
        if (!prev) {
          return fastData as TelemetryData
        }

        return {
          ...prev,
          cpu: fastData.cpu ?? prev.cpu,
          memory: fastData.memory ?? prev.memory,
        }
      })
    }

    if ((window as any).ipcRenderer) {
      (window as any).ipcRenderer.on('telemetry_fast', handleFastTelemetry)
    }

    socket.on('log', (data: { message: string }) => {
      addLog(data.message)
    })

    socket.on('state_change', (data: { state: any }) => {
      setSystemState(data.state)
      isSpeakingRef.current = (data.state === 'SPEAKING')
    })

    socket.on('scene_change', (data: { mode: string; color: string }) => {
      setCurrentScene(data)
      addLog(`Scene transition detected: ${data.mode}`)
    })

    socket.on('wake_trigger', () => {
      if (isSpeakingRef.current) return;
      setIsListening(prev => {
        if (!prev) {
          window.dispatchEvent(new CustomEvent('force-mic-start'))
          return true;
        }
        return prev;
      })
    })


    socket.on("vision_status", (data) => {
      setVisionEnabled(data.enabled)
    })

    socket.emit("get_vision_status")

    socket.on('wake_word_detected', () => {
      if (isSpeakingRef.current) return;
      // Audio Feedback: 880Hz beep, 120ms, 0.15 gain
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
      const ctx = new AudioCtx()
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.setValueAtTime(880, ctx.currentTime)
      gain.gain.setValueAtTime(0.15, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.12)
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start()
      osc.stop(ctx.currentTime + 0.12)

      // Visual Feedback: Flash white
      setWakeFlash(true)
      setTimeout(() => setWakeFlash(false), 300)
    })
    const playNextInQueue = async () => {
      if (audioQueueRef.current.length === 0) {
        isAudioPlayingRef.current = false
        // Only return to IDLE if we were SPEAKING (ignore silent greetings)
        setSystemState(prev => {
          if (prev === 'SPEAKING') {
            isSpeakingRef.current = false
            return 'IDLE'
          }
          return prev
        })
        // Restart mic if it was active before speech
        if (wasListeningBeforeSpeakRef.current) {
          wasListeningBeforeSpeakRef.current = false
          startListening()
        }
        return
      }

      isAudioPlayingRef.current = true
      const data = audioQueueRef.current.shift()!

      try {
        // Use a permanent, pre-warmed context to avoid startup dropout
        if (!playbackContextRef.current) {
          const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
          playbackContextRef.current = new AudioCtx()
        }

        if (playbackContextRef.current.state === 'suspended') {
          await playbackContextRef.current.resume()
        }

        const ctx = playbackContextRef.current
        let audioBuffer: AudioBuffer

        if (data.format === 'pcm' && data.sampleRate) {
          const binaryString = atob(data.audio)
          const bytes = new Uint8Array(binaryString.length)
          for (let i = 0; i < binaryString.length; i++) bytes[i] = binaryString.charCodeAt(i)
          const int16 = new Int16Array(bytes.buffer)
          const float32 = new Float32Array(int16.length)
          for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768.0
          audioBuffer = ctx.createBuffer(1, float32.length, data.sampleRate)
          audioBuffer.getChannelData(0).set(float32)
        } else {
          // Use decodeAudioData for MP3 to ensure sample-accurate playback and zero-latency starts
          const binaryString = atob(data.audio)
          const bytes = new Uint8Array(binaryString.length)
          for (let i = 0; i < binaryString.length; i++) bytes[i] = binaryString.charCodeAt(i)

          // Note: decodeAudioData consumes the buffer, so we pass a copy/slice if needed, 
          // but here we are done with 'bytes' anyway.
          audioBuffer = await ctx.decodeAudioData(bytes.buffer)
        }

        const source = ctx.createBufferSource()
        source.buffer = audioBuffer
        source.connect(ctx.destination)
        currentSourceRef.current = source

        if (!data.silent) {
          setSystemState('SPEAKING')
          isSpeakingRef.current = true
        }

        // Disable mic tracks while speaking
        if (microphoneRef.current && microphoneRef.current.mediaStream) {
          microphoneRef.current.mediaStream.getAudioTracks().forEach(t => t.enabled = false)
        }

        source.onended = () => {
          if (currentSourceRef.current === source) {
            currentSourceRef.current = null

            // Wait 1500ms before re-enabling mic
            // Keep isSpeakingRef.current = true during this dead zone
            setTimeout(() => {
              isSpeakingRef.current = false
              if (microphoneRef.current && microphoneRef.current.mediaStream) {
                microphoneRef.current.mediaStream.getAudioTracks().forEach(t => t.enabled = true)
              }
              playNextInQueue()
            }, 1500)
          }
        }
        source.start()
      } catch (e) {
        console.error("Audio Pipeline Error:", e)
        // Attempt to skip corrupted chunk and continue
        playNextInQueue()
      }
    }

    socket.on('speak', (data: { audio: string, format: string, sampleRate?: number, silent?: boolean }) => {
      // Guard: Stop mic if listening to avoid self-capture
      if (isListening) {
        wasListeningBeforeSpeakRef.current = true
        stopListening()
      }

      audioQueueRef.current.push(data)
      if (!isAudioPlayingRef.current) {
        playNextInQueue()
      }
    })

    return () => {
      if ((window as any).ipcRenderer) {
        (window as any).ipcRenderer.off('telemetry_fast', handleFastTelemetry)
      }
      socket.disconnect()
    }
  }, [])

  const handleInterrupt = () => {
    if (systemState === 'SPEAKING') {
      isSpeakingRef.current = false
      if (socketRef.current) socketRef.current.emit('interrupt')

      // Stop Web Audio API playback
      if (currentSourceRef.current) {
        try { currentSourceRef.current.stop(); } catch (e) { }
        currentSourceRef.current = null
      }
      audioQueueRef.current = []

      // Legacy support for user's requested audioRef if they want to use it elsewhere
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.currentTime = 0
      }

      setSystemState('IDLE')
      addLog('⚠️ Interrupt triggered.')
    }
  }

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleInterrupt()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [systemState])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
    setLogs(prev => [...prev.slice(-49), { id: Date.now().toString() + Math.random(), timestamp, message }])
  }

  const updateAudioLevel = () => {
    if (analyserRef.current) {
      const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount)
      analyserRef.current.getByteFrequencyData(dataArray)
      let speechSum = 0;
      for (let i = 4; i < 40; i++) speechSum += dataArray[i];
      const speechAvg = speechSum / 36;
      let noiseSum = 0;
      for (let i = 0; i < 4; i++) noiseSum += dataArray[i];
      for (let i = 100; i < 150; i++) noiseSum += dataArray[i];
      const noiseAvg = noiseSum / 54;

      const isActuallySpeech = speechAvg > (noiseAvg + 10) && speechAvg > 12;

      if (isActuallySpeech) {
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current)
          silenceTimerRef.current = null
        }
      } else if (!silenceTimerRef.current && isSpeakingRef.current) {
        silenceTimerRef.current = setTimeout(() => {
          silenceTimerRef.current = null
          if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
            mediaRecorderRef.current.requestData()
            setTimeout(() => stopListeningRef.current(), 100)
          } else {
            stopListeningRef.current()
          }
        }, 1800)
      }
    }
    if (isSpeakingRef.current) requestRef.current = requestAnimationFrame(updateAudioLevel)
  }

  const startListening = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext
      const audioContext = new AudioContextClass()
      const analyser = audioContext.createAnalyser()
      analyser.fftSize = 512
      const microphone = audioContext.createMediaStreamSource(stream)
      microphone.connect(analyser)
      audioContextRef.current = audioContext
      analyserRef.current = analyser
      microphoneRef.current = microphone
      setIsListening(true)
      setMicActive(true)
      isSpeakingRef.current = true
      requestRef.current = requestAnimationFrame(updateAudioLevel)
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      audioChunksRef.current = []
      mediaRecorder.ondataavailable = (event) => { if (event.data.size > 0) audioChunksRef.current.push(event.data) }
      mediaRecorder.onstop = () => {
        if (audioChunksRef.current.length > 0) {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' })

          // Guard: Do not send to backend if we are already speaking
          // This uses isSpeakingRef to catch async trail audio
          if (!isSpeakingRef.current) {
            // Check minimum audio length (5000 bytes)
            if (audioBlob.size < 5000) {
              console.log("[MicGuard] Audio too short, discarding:", audioBlob.size, "bytes")
              setMicActive(false)
            } else {
              setMicActive(false)
              if (socketRef.current) socketRef.current.emit('user_audio', audioBlob)
            }
          } else {
            console.log("[MicGuard] Dropped self-capture audio chunk.")
          }

          audioChunksRef.current = []
        }
      }
      mediaRecorder.start()
      mediaRecorderRef.current = mediaRecorder
    } catch (err) {
      addLog('Failed to access microphone.')
    }
  }

  const stopListening = () => {
    if (requestRef.current) cancelAnimationFrame(requestRef.current)
    if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null; }
    isSpeakingRef.current = false
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') mediaRecorderRef.current.stop()
    if (microphoneRef.current) {
      microphoneRef.current.mediaStream.getTracks().forEach((track: any) => track.stop())
      microphoneRef.current.disconnect()
    }
    if (audioContextRef.current) audioContextRef.current.close()
    setIsListening(false)
    setMicActive(false)
  }
  stopListeningRef.current = stopListening

  const toggleListening = () => isListening ? stopListening() : startListening()

  useEffect(() => {
    const handleForceStart = () => { if (!isListening) startListening() }
    window.addEventListener('force-mic-start', handleForceStart)
    return () => window.removeEventListener('force-mic-start', handleForceStart)
  }, [isListening])

  const handleTextSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputText.trim()) return

    const lowerText = inputText.toLowerCase().trim()
    if ((lowerText === 'stop' || lowerText === 'cancel') && systemState === 'SPEAKING') {
      handleInterrupt()
      setInputText('')
      return
    }

    if (socketRef.current) socketRef.current.emit('user_command', { text: inputText })
    setInputText('')
  }

  const cpuUsage = telemetry?.cpu?.stats?.avg_usage_percentage ?? 0
  const memoryUsage = telemetry?.memory?.stats?.memory_usage_percentage ?? 0
  const diskUsage = telemetry?.disk?.stats?.overall_usage_percent ?? 0
  const networkDown = telemetry?.network?.stats?.download_mbps ?? 0
  const networkUp = telemetry?.network?.stats?.upload_mbps ?? 0
  const batteryPct = telemetry?.battery?.stats?.percent
  const ramTotal = telemetry?.memory?.stats?.total_memory_gb ?? 0
  const ramUsed = ramTotal * (memoryUsage / 100)
  const diskUsed = telemetry?.disk?.stats?.used_space_gb ?? 0
  const diskTotal = telemetry?.disk?.stats?.total_space_gb ?? 0
  const gpuUsage = telemetry?.gpu?.nvidia?.usage_percentage ?? telemetry?.gpu?.intel?.usage_percentage ?? 0
  const gpuTemp = telemetry?.gpu?.nvidia?.temperature ?? telemetry?.gpu?.stats?.temperature ?? 0

  // Weighted composite keeps the top-line health signal stable and readable.
  const weightedLoad = cpuUsage * 0.45 + memoryUsage * 0.35 + diskUsage * 0.2
  const systemHealth = Math.max(0, Math.min(100, 100 - weightedLoad))
  const isVegaSpeaking = systemState === 'SPEAKING'

  const getLogType = (message: string): LogType => {
    const lower = message.toLowerCase()
    if (lower.includes('[vega]') || lower.includes('vega online') || lower.includes('assistant')) return 'vega'
    if (lower.includes('[user]') || lower.startsWith('user:') || lower.includes('user command')) return 'user'
    if (lower.includes('scene transition')) return 'scene'
    if (lower.includes('error') || lower.includes('failed') || lower.includes('exception')) return 'error'
    if (lower.includes('warning') || lower.includes('disconnected') || lower.includes('interrupt')) return 'warning'
    return 'system'
  }

  return (
    <div className="hud-container">
      <TitleBar />
      <HeaderStrip
        systemHealth={systemHealth}
        currentScene={currentScene}
        socketStatus={socketStatus}
        visionEnabled={visionEnabled}
      />

      <div className="hud-content">
        <TelemetryPanel
          cpuUsage={cpuUsage}
          memoryUsage={memoryUsage}
          diskUsage={diskUsage}
          ramUsed={ramUsed}
          ramTotal={ramTotal}
          diskUsed={diskUsed}
          diskTotal={diskTotal}
          gpuUsage={gpuUsage}
          gpuTemp={gpuTemp}
          networkDown={networkDown}
          networkUp={networkUp}
          batteryPct={batteryPct ?? 0}
          batteryPlugged={telemetry?.battery?.stats?.power_plugged ?? false}
          logicalCores={telemetry?.cpu?.stats?.logical_cores ?? 0}
        />

        <VoiceCorePanel
          isListening={isListening}
          isVegaSpeaking={isVegaSpeaking}
          micActive={micActive}
          wakeFlash={wakeFlash}
          systemState={systemState}
          networkDown={networkDown}
          networkUp={networkUp}
          memoryUsage={memoryUsage}
          batteryPct={batteryPct}
          inputText={inputText}
          onInputChange={setInputText}
          onToggleListening={toggleListening}
          onTextSubmit={handleTextSubmit}
        />

        <LogsPanel logs={logs} getLogType={getLogType} />
      </div>
    </div>
  )
}

export default App
