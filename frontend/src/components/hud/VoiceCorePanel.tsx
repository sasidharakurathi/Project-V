import { Mic, MicOff, Send, Wifi, BatteryMedium, Database } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

interface VoiceCorePanelProps {
  isListening: boolean
  isVegaSpeaking: boolean
  micActive: boolean
  wakeFlash: boolean
  systemState: 'IDLE' | 'LISTENING' | 'PROCESSING' | 'SPEAKING'
  networkDown: number
  networkUp: number
  memoryUsage: number
  batteryPct?: number
  inputText: string
  onInputChange: (value: string) => void
  onToggleListening: () => void
  onTextSubmit: (e: React.FormEvent) => void
}

type VegaState = 'IDLE' | 'LISTENING' | 'SPEAKING' | 'PROCESSING'

const stateConfig: Record<VegaState, { label: string; sub: string; titleClass: string; orbFrameClass: string; orbButtonClass: string }> = {
  IDLE: {
    label: 'SYSTEM IDLE',
    sub: 'All systems nominal. Ready for activation.',
    titleClass: 'title-idle',
    orbFrameClass: 'orb-frame-idle',
    orbButtonClass: 'orb-button-idle',
  },
  LISTENING: {
    label: 'AWAITING COMMAND',
    sub: 'Microphone active. Listening...',
    titleClass: 'title-listening',
    orbFrameClass: 'orb-frame-listening',
    orbButtonClass: 'orb-button-listening',
  },
  SPEAKING: {
    label: 'SPEAKING',
    sub: 'Vega is responding...',
    titleClass: 'title-idle',
    orbFrameClass: 'orb-frame-speaking',
    orbButtonClass: 'orb-button-speaking',
  },
  PROCESSING: {
    label: 'PROCESSING',
    sub: 'Analyzing input. Please wait...',
    titleClass: 'title-processing',
    orbFrameClass: 'orb-frame-processing',
    orbButtonClass: 'orb-button-processing',
  },
}

export const VoiceCorePanel = ({
  isListening,
  isVegaSpeaking,
  micActive,
  wakeFlash,
  systemState,
  networkDown,
  networkUp,
  memoryUsage,
  batteryPct,
  inputText,
  onInputChange,
  onToggleListening,
  onTextSubmit,
}: VoiceCorePanelProps) => {
  const config = stateConfig[systemState as VegaState]

  return (
    <div className="panel center-panel">
      <div className="voice-core">
        <div className="orb-wrapper">
          {(isListening || isVegaSpeaking) && (
            <>
              <motion.div className="orb-ripple" animate={{ scale: [1, 1.4, 1], opacity: [0.6, 0, 0] }} transition={{ duration: 1.5, repeat: Infinity }} />
              <motion.div className="orb-ripple delay" animate={{ scale: [1, 1.6, 1], opacity: [0.4, 0, 0] }} transition={{ duration: 2, repeat: Infinity, delay: 0.5 }} />
            </>
          )}

          <div className={`orb-frame ${config.orbFrameClass}`}>
            <div className="orb-spinner">
              <span className="orb-dot orb-dot-top" />
              <span className="orb-dot orb-dot-bottom" />
            </div>
            <div className="orb-middle-ring">
              <motion.button
                type="button"
                className={`voice-orb ${config.orbButtonClass}`}
                onClick={onToggleListening}
                aria-label={isListening ? 'Stop listening' : 'Start listening'}
                style={wakeFlash ? { backgroundColor: '#fff', boxShadow: '0 0 20px #fff' } : {}}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                {micActive ? <Mic size={24} color="#f5ffff" /> : <MicOff size={24} color="#84a5b2" />}
              </motion.button>
            </div>
          </div>
        </div>

        <h3 className={`center-title ${config.titleClass}`}>{config.label}</h3>
        <p className="subtitle">{config.sub}</p>

        <div className="voice-activity-inline">
          <span className="voice-activity-label">Vega Voice Output</span>
          <AnimatePresence mode="wait">
            {isVegaSpeaking ? (
              <motion.div
                key="vega-wave"
                className="va-bars"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.2 }}
              >
                {Array.from({ length: 24 }).map((_, i) => (
                  <motion.div
                    key={i}
                    className="va-bar"
                    animate={{
                      height: [4, 12 + ((i % 6) * 3), 7 + ((i % 4) * 2), 18 + ((i % 5) * 2), 4],
                      opacity: [0.45, 1, 0.75, 1, 0.45]
                    }}
                    transition={{
                      duration: 0.9 + (i % 5) * 0.12,
                      repeat: Infinity,
                      ease: 'easeInOut',
                      delay: i * 0.03
                    }}
                  />
                ))}
              </motion.div>
            ) : (
              <motion.div
                key="vega-idle"
                className="va-idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
              >
                Output monitor armed. Awaiting Vega speech.
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="core-metrics" aria-label="Core runtime metrics">
          <div className="core-chip"><Wifi size={10} /> <span>NET {networkDown.toFixed(1)}↓ {networkUp.toFixed(1)}↑</span></div>
          <div className="core-chip"><Database size={12} /> <span>RAM {memoryUsage.toFixed(0)}%</span></div>
          <div className="core-chip"><BatteryMedium size={12} /> <span>PWR {typeof batteryPct === 'number' ? `${batteryPct.toFixed(0)}%` : 'N/A'}</span></div>
        </div>

        <form className="text-input-form" onSubmit={onTextSubmit}>
          <input type="text" className="text-input" placeholder="Type a command manually..." value={inputText} onChange={(e) => onInputChange(e.target.value)} />
          <button type="submit" className="text-submit-btn" disabled={!inputText.trim()}><Send size={14} color={inputText.trim() ? '#06b6d4' : '#4b5563'} /></button>
        </form>
      </div>
    </div>
  )
}
