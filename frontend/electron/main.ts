import { app, BrowserWindow, ipcMain } from 'electron'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
process.env.APP_ROOT = join(__dirname, '..')

export const VITE_DEV_SERVER_URL = process.env['VITE_DEV_SERVER_URL']
export const MAIN_DIST = join(process.env.APP_ROOT, 'dist-electron')
export const RENDERER_DIST = join(process.env.APP_ROOT, 'dist')

process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL ? join(process.env.APP_ROOT, 'public') : RENDERER_DIST

let win: BrowserWindow | null
let splashWin: BrowserWindow | null

function createSplashWindow() {
    splashWin = new BrowserWindow({
        width: 500,
        height: 400,
        transparent: true,
        frame: false,
        alwaysOnTop: true,
        resizable: false,
        icon: join(process.env.VITE_PUBLIC || '', 'vite.svg'),
        webPreferences: {
            preload: join(__dirname, 'preload.mjs'),
            contextIsolation: true,
        },
    })

    splashWin.loadFile(join(process.env.VITE_PUBLIC || '', 'splash.html'))
}

function createWindow() {
    win = new BrowserWindow({
        icon: join(process.env.VITE_PUBLIC || '', 'vite.svg'),
        width: 1200,
        height: 800,
        show: false,
        backgroundColor: '#050505',
        frame: false, // Make window frameless
        webPreferences: {
            preload: join(__dirname, 'preload.mjs'),
            contextIsolation: true,
        },
    })

    // Test active push message to Renderer-process.
    win.webContents.on('did-finish-load', () => {
        win?.webContents.send('main-process-message', (new Date).toLocaleString())
    })

    if (VITE_DEV_SERVER_URL) {
        win.loadURL(VITE_DEV_SERVER_URL)
    } else {
        win.loadFile(join(RENDERER_DIST, 'index.html'))
    }
}

import { exec } from 'node:child_process'

function spawnPythonBackend() {
    const backendPath = join(process.env.APP_ROOT || '', '..', 'backend', 'main.py')
    // Use python from the venv if available, otherwise fallback
    const pythonExecutable = process.platform === 'win32'
        ? join(process.env.APP_ROOT || '', '..', 'backend', 'venv', 'Scripts', 'python.exe')
        : join(process.env.APP_ROOT || '', '..', 'backend', 'venv', 'bin', 'python')

    console.log(`[Vega System]: Requesting UAC Administrator elevation for python backend via PowerShell...`)

    // On Windows, use PowerShell's Start-Process with the RunAs verb to trigger native UAC
    if (process.platform === 'win32') {
        const backendDir = join(process.env.APP_ROOT || '', '..', 'backend')
        // Wrap paths in triple quotes/escaped quotes so PowerShell handles spaces in "Project V" correctly
        const psCommand = `powershell.exe -Command "Start-Process '${pythonExecutable}' -ArgumentList '\\"${backendPath}\\"' -WorkingDirectory '${backendDir}' -Verb RunAs -WindowStyle Hidden"`
        exec(psCommand, (error, stdout, stderr) => {
            if (error) {
                console.error(`[powershell elevation error]: ${error}`)
            }
            if (stdout) console.log(`[powershell stdout]: ${stdout}`)
            if (stderr) console.error(`[powershell stderr]: ${stderr}`)
        })
    } else {
        // Fallback for mac/linux
        exec(`"${pythonExecutable}" "${backendPath}"`)
    }
}

function startBackendHeartbeat() {
    // Send a ping every 5 seconds to keep the backend alive
    setInterval(() => {
        fetch('http://127.0.0.1:8000/api/ping')
            .catch(() => { /* Silent failure, backend might be starting or already dead */ });
    }, 5000)
}

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit()
        win = null
    }
})

app.on('before-quit', () => {
    console.log('[Vega System]: Sending shutdown signal to elevated Python backend...')
    fetch('http://127.0.0.1:8000/api/shutdown', { method: 'POST' })
        .catch(err => console.error('Failed to shutdown Python process:', err))
})

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow()
    }
})

app.whenReady().then(() => {
    spawnPythonBackend()
    startBackendHeartbeat()
    createSplashWindow()
    createWindow()

    ipcMain.on('splash-telemetry', (_event, data) => {
        if (splashWin) {
            splashWin.webContents.send('telemetry', data)
        }
    })

    // Wait for the React app to connect to the Python backend and render its widgets
    let appReadyFired = false

    const showMainApp = () => {
        if (appReadyFired) return
        appReadyFired = true

        if (splashWin) {
            splashWin.close()
            splashWin = null
        }
        if (win) {
            win.maximize()
            win.show()
        }
    }

    // Primary trigger: React IPC signal
    ipcMain.once('app-ready', showMainApp)

    // Handle custom close button quit
    ipcMain.on('quit-app', async () => {
        console.log('[Vega System]: Quit command received from Custom UI. Shutting down...')
        try {
            // Signal python to die first
            await fetch('http://127.0.0.1:8000/api/shutdown', { method: 'POST' })
        } catch (e) {
            console.error('Failed to signal backend shutdown:', e)
        }
        app.quit()
    })

    // Failsafe trigger: 10 second timeout if IPC gets blocked by context isolation
    setTimeout(showMainApp, 10000)
})
