import win32gui
import win32con
import win32api
import win32process


def _find_window_by_title(partial_title: str):
    """Helper to find a window handle by a partial title match."""
    matched_hwnds = []

    def enum_windows_proc(hwnd, lParam):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            title = win32gui.GetWindowText(hwnd)
            search_tokens = partial_title.lower().split()
            title_lower = title.lower()

            # Simple substring match OR token match
            if partial_title.lower() in title_lower or all(
                token in title_lower for token in search_tokens
            ):
                matched_hwnds.append((hwnd, title))
        return True

    win32gui.EnumWindows(enum_windows_proc, 0)

    if not matched_hwnds:
        return None, None

    # Return the first match
    return matched_hwnds[0]


def list_open_windows() -> str:
    """Returns a list of all currently open and visible window titles."""
    titles = []

    def enum_windows_proc(hwnd, lParam):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            # Ignore some system windows but we keep it simple here
            title = win32gui.GetWindowText(hwnd)
            if title not in titles:
                titles.append(title)
        return True

    win32gui.EnumWindows(enum_windows_proc, 0)
    return "Open Windows:\n" + "\n".join(f"- {t}" for t in titles if t.strip())


def switch_focus(app_name: str) -> str:
    """Brings the specified application window to the foreground."""
    hwnd, title = _find_window_by_title(app_name)
    if not hwnd:
        return f"Could not find any open window matching '{app_name}'."

    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # Windows 10/11 prevents background apps from stealing focus.
        # We must attach our thread input to the currently focused window's thread.
        foreground_hwnd = win32gui.GetForegroundWindow()
        if foreground_hwnd and foreground_hwnd != hwnd:
            fg_thread_id, _ = win32process.GetWindowThreadProcessId(foreground_hwnd)
            current_thread_id = win32api.GetCurrentThreadId()

            # Attach input processing mechanism
            win32process.AttachThreadInput(current_thread_id, fg_thread_id, True)

            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
            )
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_NOTOPMOST,
                0,
                0,
                0,
                0,
                win32con.SWP_SHOWWINDOW | win32con.SWP_NOMOVE | win32con.SWP_NOSIZE,
            )

            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)

            # Detach immediately
            win32process.AttachThreadInput(current_thread_id, fg_thread_id, False)
        else:
            win32gui.SetForegroundWindow(hwnd)

        return f"Successfully switched focus to: {title}"
    except Exception as e:
        return f"Error switching focus to {title}: {e}"


def close_app(app_name: str) -> str:
    """Gracefully closes the specified application window."""
    hwnd, title = _find_window_by_title(app_name)
    if not hwnd:
        return f"Could not find any open window matching '{app_name}'."

    try:
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        return f"Sent close signal to: {title}"
    except Exception as e:
        return f"Error closing {title}: {e}"


def snap_window(app_name: str, position: str) -> str:
    """
    Snaps a window. Position can be 'left', 'right', 'maximize', or 'minimize'.
    """
    hwnd, title = _find_window_by_title(app_name)
    if not hwnd:
        return f"Could not find any open window matching '{app_name}'."

    position = position.lower()

    try:
        if position == "minimize":
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return f"Minimized {title}"
        elif position == "maximize":
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return f"Maximized {title}"

        # Get screen dimensions for left/right snapping
        screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

        # Restore if maximized or minimized
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        if position == "left":
            win32gui.MoveWindow(hwnd, 0, 0, screen_width // 2, screen_height, True)
            return f"Snapped {title} to the left."
        elif position == "right":
            win32gui.MoveWindow(
                hwnd, screen_width // 2, 0, screen_width // 2, screen_height, True
            )
            return f"Snapped {title} to the right."
        else:
            return f"Invalid snap position: {position}. Use 'left', 'right', 'maximize', or 'minimize'."
    except Exception as e:
        return f"Error snapping {title}: {e}"


def resize_window(app_name: str, width: int, height: int) -> str:
    """Resizes a window to the specified width and height in pixels."""
    hwnd, title = _find_window_by_title(app_name)
    if not hwnd:
        return f"Could not find any open window matching '{app_name}'."

    try:
        # Restore if maximized or minimized
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # Get current position
        rect = win32gui.GetWindowRect(hwnd)
        x, y = rect[0], rect[1]

        win32gui.MoveWindow(hwnd, x, y, width, height, True)
        return f"Resized {title} to {width}x{height} pixels."
    except Exception as e:
        return f"Error resizing {title}: {e}"
