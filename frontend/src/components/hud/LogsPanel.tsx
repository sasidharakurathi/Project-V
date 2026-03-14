import { useEffect, useRef } from 'react'
import { Terminal } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'

interface LogMessage {
  id: string
  timestamp: string
  message: string
}

type LogType = 'system' | 'vega' | 'user' | 'scene' | 'warning' | 'error'

interface LogsPanelProps {
  logs: LogMessage[]
  getLogType: (message: string) => LogType
}



export const LogsPanel = ({ logs, getLogType }: LogsPanelProps) => {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs])

  return (
    <div className="panel log-panel">
      <div className="panel-header">
        <Terminal size={16} color="#10b981" />
        <h2>System Logs</h2>
        <span className="log-count">{logs.length} entries</span>
      </div>
      <div className="panel-body log-list" ref={scrollRef} style={{ flex: 1, overflowY: 'auto' }}>
        <AnimatePresence>
          {logs.map((log, i) => {
            const type = getLogType(log.message)
            return (
              <motion.div
                key={log.id}
                className={`log-entry log-${type}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i * 0.02, 0.2) }}
              >
                <span className="log-time">{log.timestamp}</span>
                <span className={`log-type log-type-${type}`}>{type}</span>
                <span className="log-msg">{log.message}</span>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </div>
  )
}
