import { useState, useEffect, useRef } from 'react'
import { Mic, MicOff, Search, Monitor, Mail, FileText, Settings, Key, Globe, LayoutDashboard, Terminal, Activity, Send, Cpu, Database, HardDrive, MonitorPlay, Wifi, BatteryMedium, Zap, Eye, EyeOff } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import io, { Socket } from 'socket.io-client'
import { TitleBar } from './components/TitleBar'
import './App.css'

interface Skill {
  id: string
  name: string
  description: string
  icon: React.ElementType
  color: string
}

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

const UPCOMING_SKILLS: Skill[] = [
  { id: 'os', name: 'OS Automation', description: 'Control Windows apps and settings', icon: Monitor, color: '#3b82f6' },
  { id: 'web', name: 'Web Browsing', description: 'Search and interact with websites', icon: Globe, color: '#10b981' },
  { id: 'data', name: 'Data Extraction', description: 'Extract text from images and docs', icon: FileText, color: '#f59e0b' },
  { id: 'comm', name: 'Email & Comm', description: 'Draft and manage communications', icon: Mail, color: '#8b5cf6' },
  { id: 'search', name: 'Deep Search', description: 'Find files and hidden data', icon: Search, color: '#ec4899' },
  { id: 'creds', name: 'Credential Vault', description: 'Manage API keys securely', icon: Key, color: '#64748b' },
]

function App() {
  const [isListening, setIsListening] = useState(false)
  const [systemState, setSystemState] = useState<'IDLE' | 'LISTENING' | 'PROCESSING' | 'SPEAKING'>('IDLE')
  const [socketStatus, setSocketStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting')
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null)
  const [currentScene, setCurrentScene] = useState<{ mode: string; color: string }>({ mode: 'IDLE', color: '#64748b' })
  const [logs, setLogs] = useState<LogMessage[]>([])
  const [audioLevel, setAudioLevel] = useState<number>(0)
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
      setAudioLevel(speechAvg)

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
    setAudioLevel(0)
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

  return (
    <div className="hud-container">
      <TitleBar />
      <header className="hud-header">
        <div className="header-left">
          <LayoutDashboard size={18} color="#e4e4e7" />
          <h1>VEGA HUD</h1>
        </div>
        <div className="header-right">
          <div className="scene-badge" style={{ borderColor: currentScene.color }}>
            <span className="scene-label">SCENE:</span>
            <span className="scene-mode" style={{ color: currentScene.color }}>{currentScene.mode}</span>
          </div>
          <div className="status-badge">
            <div className={`status-dot ${socketStatus}`} />
            <span>{socketStatus}</span>
          </div>
          <div className={`vision-indicator ${visionEnabled ? 'enabled' : 'disabled'}`} style={{ marginRight: '8px', display: 'flex', alignItems: 'center' }}>
            {visionEnabled ? (
              <Eye size={16} color="#22c55e" style={{ filter: 'drop-shadow(0 0 5px #22c55e)' }} />
            ) : (
              <EyeOff size={16} color="#64748b" />
            )}
          </div>
          <button className="icon-btn"><Settings size={16} /></button>
        </div>
      </header>

      <div className="hud-content">
        <div className="panel telemetry-panel">
          <div className="panel-header">
            <Activity size={16} color="#3b82f6" />
            <h2>System Telemetry</h2>
          </div>
          <div className="panel-body telemetry-stats">
            <div className="stat-box"><div className="stat-box-header"><Cpu size={12} /> <span>CPU</span></div>
              <div className="stat-box-value">{telemetry?.cpu?.stats?.avg_usage_percentage?.toFixed(1) || '0.0'}<span className="stat-sub">%</span></div>
            </div>
            <div className="stat-box"><div className="stat-box-header"><Database size={12} /> <span>RAM</span></div>
              <div className="stat-box-value">{((telemetry?.memory?.stats?.total_memory_gb || 0) * ((telemetry?.memory?.stats?.memory_usage_percentage || 0) / 100)).toFixed(1)} <span className="stat-sub">/ {telemetry?.memory?.stats?.total_memory_gb?.toFixed(1) || '0.0'} GB</span></div>
            </div>
            <div className="stat-box"><div className="stat-box-header"><HardDrive size={12} /> <span>DISK</span></div>
              <div className="stat-box-value">{telemetry?.disk?.stats?.used_space_gb?.toFixed(0) || '0'} <span className="stat-sub">/ {telemetry?.disk?.stats?.total_space_gb?.toFixed(0) || '0'} GB</span></div>
            </div>
            {telemetry?.gpu?.nvidia && (
              <div className="stat-box"><div className="stat-box-header"><MonitorPlay size={12} /> <span>dGPU</span></div>
                <div className="stat-box-value">{telemetry.gpu.nvidia.usage_percentage?.toFixed(1) ?? '0.0'}<span className="stat-sub">% • {telemetry.gpu.nvidia.temperature?.toFixed(0) ?? '0'}°C</span></div>
              </div>
            )}
            {telemetry?.gpu?.intel && (
              <div className="stat-box"><div className="stat-box-header"><MonitorPlay size={12} /> <span>iGPU</span></div>
                <div className="stat-box-value">{telemetry.gpu.intel.usage_percentage?.toFixed(1) ?? '0.0'}<span className="stat-sub">%</span></div>
              </div>
            )}
            {telemetry?.network && (
              <div className="stat-box"><div className="stat-box-header"><Wifi size={12} /> <span>NET</span></div>
                <div className="stat-box-value"><span className="stat-sub">↓</span>{telemetry.network.stats.download_mbps?.toFixed(1)} <span className="stat-sub">↑</span>{telemetry.network.stats.upload_mbps?.toFixed(1)}</div>
              </div>
            )}
            {telemetry?.battery && (
              <div className="stat-box"><div className="stat-box-header"><BatteryMedium size={12} /> <span>PWR</span></div>
                <div className="stat-box-value">{telemetry.battery.stats.percent?.toFixed(0)}<span className="stat-sub">%</span> {telemetry.battery.stats.power_plugged && <Zap size={10} color="#f59e0b" style={{ marginLeft: 4, display: 'inline-block' }} />}</div>
              </div>
            )}

            <div className="waveform-container">
              <span className="stat-label" style={{ marginBottom: '12px', display: 'block' }}>Voice Activity</span>
              <div className="bars">
                {Array.from({ length: 15 }).map((_, i) => {
                  const centerIndex = 7;
                  const distance = Math.abs(i - centerIndex);
                  const maxMultiplier = 1 - (distance * 0.1);
                  const baseHeight = 4;
                  const activeHeight = (isListening || systemState === 'SPEAKING') ? Math.max(baseHeight, maxMultiplier * (isListening ? audioLevel : 40) * 0.8) : baseHeight;
                  return (
                    <motion.div key={i} className="bar" animate={{ height: activeHeight }} transition={{ type: "spring", stiffness: 300, damping: 20 }} />
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        <div className="panel center-panel">
          <div className="voice-core">
            <div className="orb-wrapper" onClick={toggleListening}>
              {(isListening || systemState === 'SPEAKING') && (
                <>
                  <motion.div className="orb-ripple" animate={{ scale: [1, 1.4, 1], opacity: [0.6, 0, 0] }} transition={{ duration: 1.5, repeat: Infinity }} />
                  <motion.div className="orb-ripple delay" animate={{ scale: [1, 1.6, 1], opacity: [0.4, 0, 0] }} transition={{ duration: 2, repeat: Infinity, delay: 0.5 }} />
                </>
              )}
              <motion.div
                className={`voice-orb ${micActive ? 'active' : ''}`}
                style={wakeFlash ? { backgroundColor: '#fff', boxShadow: '0 0 20px #fff' } : {}}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                {micActive ? <Mic size={28} color="#fff" /> : <MicOff size={28} color="#a1a1aa" />}
              </motion.div>
              <AnimatePresence>
                {systemState === 'SPEAKING' && (
                  <motion.div
                    className="sound-wave"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    transition={{ duration: 0.2 }}
                  >
                    <div className="bar bar-1" />
                    <div className="bar bar-2" />
                    <div className="bar bar-3" />
                    <div className="bar bar-4" />
                    <div className="bar bar-5" />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            <h3>
              {systemState === 'IDLE' ? 'System Idle' :
                systemState === 'LISTENING' ? 'Awaiting Command...' :
                  systemState === 'SPEAKING' ? 'Speaking...' :
                    'Processing...'}
            </h3>
            <p className="subtitle">
              {systemState === 'IDLE' ? 'Say "Vega" or click orb to initialize' :
                systemState === 'LISTENING' ? 'Listening to audio stream...' :
                  systemState === 'SPEAKING' ? 'Emitting vocal response...' :
                    'Routing agent logic...'}
            </p>

            <form className="text-input-form" onSubmit={handleTextSubmit}>
              <input type="text" className="text-input" placeholder="Type a command manually..." value={inputText} onChange={(e) => setInputText(e.target.value)} />
              <button type="submit" className="text-submit-btn" disabled={!inputText.trim()}><Send size={14} color={inputText.trim() ? "#06b6d4" : "#4b5563"} /></button>
            </form>
          </div>

          <div className="mini-skills">
            {UPCOMING_SKILLS.map(skill => (
              <div className="mini-skill-btn" key={skill.id} onClick={() => addLog(`Skill Triggered: ${skill.name}`)}>
                <skill.icon size={16} color={skill.color} />
                <span>{skill.name}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel log-panel">
          <div className="panel-header"><Terminal size={16} color="#10b981" /><h2>System Logs</h2></div>
          <div className="panel-body log-list" style={{ flex: 1 }}>
            <AnimatePresence>
              {logs.map(log => (
                <motion.div key={log.id} className="log-entry" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
                  <span className="log-time">[{log.timestamp}]</span>
                  <span className="log-msg">{log.message}</span>
                </motion.div>
              ))}
            </AnimatePresence>
            <div ref={logsEndRef} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
