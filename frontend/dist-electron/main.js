import { app, BrowserWindow, ipcMain } from "electron";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import os from "node:os";
import { exec } from "node:child_process";
const __dirname$1 = dirname(fileURLToPath(import.meta.url));
process.env.APP_ROOT = join(__dirname$1, "..");
const VITE_DEV_SERVER_URL = process.env["VITE_DEV_SERVER_URL"];
const MAIN_DIST = join(process.env.APP_ROOT, "dist-electron");
const RENDERER_DIST = join(process.env.APP_ROOT, "dist");
process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL ? join(process.env.APP_ROOT, "public") : RENDERER_DIST;
let win;
let splashWin;
let fastTelemetryTimer = null;
let prevCpuSnapshot = os.cpus();
function computeCpuUsagePercent() {
  const current = os.cpus();
  let idleDelta = 0;
  let totalDelta = 0;
  for (let i = 0; i < current.length; i++) {
    const prevTimes = prevCpuSnapshot[i].times;
    const nowTimes = current[i].times;
    const prevTotal = prevTimes.user + prevTimes.nice + prevTimes.sys + prevTimes.idle + prevTimes.irq;
    const nowTotal = nowTimes.user + nowTimes.nice + nowTimes.sys + nowTimes.idle + nowTimes.irq;
    idleDelta += nowTimes.idle - prevTimes.idle;
    totalDelta += nowTotal - prevTotal;
  }
  prevCpuSnapshot = current;
  if (totalDelta <= 0) return 0;
  return Math.max(0, Math.min(100, (totalDelta - idleDelta) / totalDelta * 100));
}
function startFastTelemetryBridge() {
  if (fastTelemetryTimer) {
    clearInterval(fastTelemetryTimer);
    fastTelemetryTimer = null;
  }
  prevCpuSnapshot = os.cpus();
  fastTelemetryTimer = setInterval(() => {
    if (!win || win.isDestroyed()) return;
    const totalMemoryBytes = os.totalmem();
    const freeMemoryBytes = os.freemem();
    const usedMemoryBytes = totalMemoryBytes - freeMemoryBytes;
    const memoryUsagePercent = totalMemoryBytes > 0 ? usedMemoryBytes / totalMemoryBytes * 100 : 0;
    const fastPayload = {
      cpu: {
        result: null,
        stats: {
          physical_cores: os.cpus().length,
          logical_cores: os.cpus().length,
          avg_usage_percentage: computeCpuUsagePercent(),
          high_usage_alert: false
        },
        additional_info: null
      },
      memory: {
        result: null,
        stats: {
          memory_usage_percentage: memoryUsagePercent,
          swap_usage_percentage: 0,
          total_memory_gb: totalMemoryBytes / 1024 ** 3,
          available_memory_gb: freeMemoryBytes / 1024 ** 3
        },
        additional_info: null
      }
    };
    win.webContents.send("telemetry_fast", fastPayload);
  }, 1500);
}
function stopFastTelemetryBridge() {
  if (fastTelemetryTimer) {
    clearInterval(fastTelemetryTimer);
    fastTelemetryTimer = null;
  }
}
function createSplashWindow() {
  splashWin = new BrowserWindow({
    width: 500,
    height: 400,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    resizable: false,
    icon: join(process.env.VITE_PUBLIC || "", "vite.svg"),
    webPreferences: {
      preload: join(__dirname$1, "preload.mjs"),
      contextIsolation: true
    }
  });
  splashWin.loadFile(join(process.env.VITE_PUBLIC || "", "splash.html"));
}
function createWindow() {
  win = new BrowserWindow({
    icon: join(process.env.VITE_PUBLIC || "", "vite.svg"),
    width: 1200,
    height: 800,
    show: false,
    backgroundColor: "#050505",
    frame: false,
    // Make window frameless
    webPreferences: {
      preload: join(__dirname$1, "preload.mjs"),
      contextIsolation: true
    }
  });
  win.webContents.on("did-finish-load", () => {
    win?.webContents.send("main-process-message", (/* @__PURE__ */ new Date()).toLocaleString());
  });
  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL);
  } else {
    win.loadFile(join(RENDERER_DIST, "index.html"));
  }
  startFastTelemetryBridge();
}
function spawnPythonBackend() {
  const backendPath = join(process.env.APP_ROOT || "", "..", "backend", "main.py");
  const pythonExecutable = process.platform === "win32" ? join(process.env.APP_ROOT || "", "..", "backend", "venv", "Scripts", "python.exe") : join(process.env.APP_ROOT || "", "..", "backend", "venv", "bin", "python");
  console.log(`[Vega System]: Requesting UAC Administrator elevation for python backend via PowerShell...`);
  if (process.platform === "win32") {
    const backendDir = join(process.env.APP_ROOT || "", "..", "backend");
    const psCommand = `powershell.exe -Command "Start-Process '${pythonExecutable}' -ArgumentList '\\"${backendPath}\\"' -WorkingDirectory '${backendDir}' -Verb RunAs -WindowStyle Hidden"`;
    exec(psCommand, (error, stdout, stderr) => {
      if (error) {
        console.error(`[powershell elevation error]: ${error}`);
      }
      if (stdout) console.log(`[powershell stdout]: ${stdout}`);
      if (stderr) console.error(`[powershell stderr]: ${stderr}`);
    });
  } else {
    exec(`"${pythonExecutable}" "${backendPath}"`);
  }
}
function startBackendHeartbeat() {
  setInterval(() => {
    fetch("http://127.0.0.1:8000/api/ping").catch(() => {
    });
  }, 5e3);
}
app.on("window-all-closed", () => {
  stopFastTelemetryBridge();
  if (process.platform !== "darwin") {
    app.quit();
    win = null;
  }
});
app.on("before-quit", () => {
  stopFastTelemetryBridge();
  console.log("[Vega System]: Sending shutdown signal to elevated Python backend...");
  fetch("http://127.0.0.1:8000/api/shutdown", { method: "POST" }).catch((err) => console.error("Failed to shutdown Python process:", err));
});
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
app.whenReady().then(() => {
  spawnPythonBackend();
  startBackendHeartbeat();
  createSplashWindow();
  createWindow();
  ipcMain.on("splash-telemetry", (_event, data) => {
    if (splashWin) {
      splashWin.webContents.send("telemetry", data);
    }
  });
  let appReadyFired = false;
  const showMainApp = () => {
    if (appReadyFired) return;
    appReadyFired = true;
    if (splashWin) {
      splashWin.close();
      splashWin = null;
    }
    if (win) {
      win.maximize();
      win.show();
    }
  };
  ipcMain.once("app-ready", showMainApp);
  ipcMain.on("window-minimize", () => {
    if (win && !win.isDestroyed()) {
      win.minimize();
    }
  });
  ipcMain.on("window-toggle-maximize", () => {
    if (win && !win.isDestroyed()) {
      if (win.isMaximized()) {
        win.unmaximize();
      } else {
        win.maximize();
      }
    }
  });
  ipcMain.on("quit-app", async () => {
    console.log("[Vega System]: Quit command received from Custom UI. Shutting down...");
    try {
      await fetch("http://127.0.0.1:8000/api/shutdown", { method: "POST" });
    } catch (e) {
      console.error("Failed to signal backend shutdown:", e);
    }
    app.quit();
  });
  setTimeout(showMainApp, 1e4);
});
export {
  MAIN_DIST,
  RENDERER_DIST,
  VITE_DEV_SERVER_URL
};
