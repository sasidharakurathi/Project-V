import { X } from 'lucide-react'

export const TitleBar = () => {
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
            <button className="close-btn" onClick={handleClose} title="Graceful Shutdown">
                <X size={18} />
            </button>
        </div>
    )
}
