import { Eye, EyeOff, Settings } from 'lucide-react'

interface HeaderStripProps {
  systemHealth: number
  currentScene: { mode: string; color: string }
  socketStatus: 'connecting' | 'connected' | 'disconnected'
  visionEnabled: boolean
}

export const HeaderStrip = ({
  systemHealth,
  currentScene,
  socketStatus,
  visionEnabled,
}: HeaderStripProps) => {
  return (
    <header className="hud-header">
      <div className="header-left">
        <img className="hud-logo" src="/vega-logo.png" alt="Vega logo" />
        <h1>VEGA HUD</h1>
      </div>
      <div className="header-right">
        <div className="health-badge" title="Weighted system health index">
          <span className="health-label">HEALTH</span>
          <span className="health-value">{systemHealth.toFixed(0)}%</span>
        </div>
        <div className="scene-badge" style={{ borderColor: currentScene.color }}>
          <span className="scene-label">SCENE</span>
          <span className="scene-mode" style={{ color: currentScene.color }}>{currentScene.mode}</span>
        </div>
        <div className="status-badge">
          <div className={`status-dot ${socketStatus}`} />
          <span>CONNECTION</span>
          <strong>{socketStatus}</strong>
        </div>
        <div className={`vision-indicator ${visionEnabled ? 'enabled' : 'disabled'}`} style={{ marginRight: '8px', display: 'flex', alignItems: 'center' }}>
          {visionEnabled ? (
            <Eye size={16} color="#22c55e" style={{ filter: 'drop-shadow(0 0 5px #22c55e)' }} />
          ) : (
            <EyeOff size={16} color="#64748b" />
          )}
        </div>
        <button className="icon-btn" aria-label="Settings">
          <Settings size={16} />
        </button>
      </div>
    </header>
  )
}
