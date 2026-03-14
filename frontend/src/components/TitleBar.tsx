import { Minus, Square, X } from 'lucide-react'

export const TitleBar = () => {
    const handleMinimize = () => {
        if ((window as any).ipcRenderer) {
            (window as any).ipcRenderer.send('window-minimize')
        }
    }

    const handleToggleMaximize = () => {
        if ((window as any).ipcRenderer) {
            (window as any).ipcRenderer.send('window-toggle-maximize')
        }
    }

    const handleClose = () => {
        if ((window as any).ipcRenderer) {
            (window as any).ipcRenderer.send('quit-app')
        }
    }

    return (
        <div className="custom-title-bar">
            <div className="title-bar-drag-area">
                <div className="title-bar-content">
                    <div className="tech-decor-left"></div>
                    <div className="app-name">VEGA <span className="sub-name">AI ASSISTANT</span></div>
                    <div className="tech-decor-right"></div>
                </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <button className="close-btn" title="Minimize" aria-label="Minimize window" style={{ opacity: 0.8 }} onClick={handleMinimize}>
                    <Minus size={14} />
                </button>
                <button className="close-btn" title="Maximize" aria-label="Maximize window" style={{ opacity: 0.8 }} onClick={handleToggleMaximize}>
                    <Square size={11} />
                </button>
                <button className="close-btn" onClick={handleClose} title="Graceful Shutdown" aria-label="Close window">
                    <X size={16} />
                </button>
            </div>
        </div>
    )
}
