import { Activity, BatteryMedium, Cpu, Database, HardDrive, MonitorPlay, Wifi } from 'lucide-react'

interface TelemetryPanelProps {
  cpuUsage: number
  memoryUsage: number
  diskUsage: number
  ramUsed: number
  ramTotal: number
  diskUsed: number
  diskTotal: number
  gpuUsage: number
  gpuTemp: number
  networkDown: number
  networkUp: number
  batteryPct: number
  batteryPlugged: boolean
  logicalCores: number
}

export const TelemetryPanel = ({
  cpuUsage,
  memoryUsage,
  diskUsage,
  ramUsed,
  ramTotal,
  diskUsed,
  diskTotal,
  gpuUsage,
  gpuTemp,
  networkDown,
  networkUp,
  batteryPct,
  batteryPlugged,
  logicalCores,
}: TelemetryPanelProps) => {
  return (
    <div className="panel telemetry-panel">
      <div className="panel-header">
        <Activity size={16} color="#3b82f6" />
        <h2>System Telemetry</h2>
      </div>
      <div className="panel-body telemetry-stats">
        <div className="stat-box stat-box-wide">
          <div className="stat-box-header"><Activity size={12} /> <span>CORE LOAD VECTOR</span></div>
          <div className="core-load-values">
            <span className="core-cpu">CPU {cpuUsage.toFixed(1)}%</span>
            <span className="core-mem">MEM {memoryUsage.toFixed(1)}%</span>
            <span className="core-disk">DSK {diskUsage.toFixed(1)}%</span>
          </div>
          <div className="core-load-bars">
            <div className="core-load-track"><span style={{ width: `${Math.min(100, cpuUsage)}%` }} /></div>
            <div className="core-load-track mem"><span style={{ width: `${Math.min(100, memoryUsage)}%` }} /></div>
            <div className="core-load-track disk"><span style={{ width: `${Math.min(100, diskUsage)}%` }} /></div>
          </div>
        </div>

        <div className="stat-box">
          <div className="stat-box-header"><Cpu size={12} /> <span>CPU</span></div>
          <div className="stat-box-value stat-main-row">
            <span className="stat-value-cyan">{cpuUsage.toFixed(1)}<span className="stat-sub">%</span></span>
            <span className="stat-dim">{logicalCores} Cores</span>
          </div>
          <div className="stat-mini-bar"><span style={{ width: `${Math.min(100, cpuUsage)}%` }} /></div>
        </div>

        <div className="stat-box">
          <div className="stat-box-header"><Database size={12} /> <span>RAM</span></div>
          <div className="stat-box-value stat-main-row">
            <span className="stat-value-amber">{memoryUsage.toFixed(1)}<span className="stat-sub">%</span></span>
            <span className="stat-dim">{ramUsed.toFixed(1)} / {ramTotal.toFixed(1)} GB</span>
          </div>
          <div className="stat-mini-bar mem"><span style={{ width: `${Math.min(100, memoryUsage)}%` }} /></div>
        </div>

        <div className="stat-box">
          <div className="stat-box-header"><HardDrive size={12} /> <span>DISK</span></div>
          <div className="stat-box-value stat-main-row">
            <span className="stat-value-green">{diskUsage.toFixed(1)}<span className="stat-sub">%</span></span>
            <span className="stat-dim">{diskUsed.toFixed(0)} / {diskTotal.toFixed(0)} GB</span>
          </div>
          <div className="stat-mini-bar disk"><span style={{ width: `${Math.min(100, diskUsage)}%` }} /></div>
        </div>

        <div className="stat-box">
          <div className="stat-box-header"><MonitorPlay size={12} /> <span>dGPU</span></div>
          <div className="stat-box-value stat-main-row">
            <span className="stat-value-cyan">{gpuUsage.toFixed(1)}<span className="stat-sub">%</span></span>
            <span className="stat-dim">{gpuTemp.toFixed(0)}°C</span>
          </div>
          <div className="stat-mini-bar"><span style={{ width: `${Math.min(100, gpuUsage)}%` }} /></div>
        </div>

        <div className="stat-box">
          <div className="stat-box-header"><Wifi size={12} /> <span>NET</span></div>
          <div className="stat-box-value stat-net-rows">
            <span><span className="stat-sub">↓</span>{networkDown.toFixed(1)} Mb/s</span>
            <span><span className="stat-sub">↑</span>{networkUp.toFixed(1)} Mb/s</span>
          </div>
        </div>

        <div className="stat-box">
          <div className="stat-box-header"><BatteryMedium size={12} /> <span>PWR</span></div>
          <div className="stat-box-value stat-main-row">
            <span className="stat-value-amber">{batteryPct.toFixed(0)}<span className="stat-sub">%</span></span>
            <span className="stat-dim">{batteryPlugged ? 'AC' : 'BAT'}</span>
          </div>
          <div className="stat-mini-bar mem"><span style={{ width: `${Math.min(100, batteryPct)}%` }} /></div>
        </div>
      </div>
    </div>
  )
}
