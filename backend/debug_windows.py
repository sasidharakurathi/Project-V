import win32gui
import json


def get_active_window_titles():
    titles = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and len(title) > 2:
                titles.append(title)

    win32gui.EnumWindows(callback, None)
    return titles


if __name__ == "__main__":
    titles = get_active_window_titles()
    print(f"Detected {len(titles)} windows:")
    for t in titles:
        print(f"- {t}")
