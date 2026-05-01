from __future__ import annotations

import ctypes


def ensure_windows_dpi_aware() -> str:
    """
    Tenta registrar o processo como DPI-aware no Windows para reduzir
    divergencias entre coordenadas reais da tela e o que a automacao visual enxerga.
    """
    if not hasattr(ctypes, "windll"):
        return "unsupported"

    user32 = ctypes.windll.user32

    try:
        awareness_context_per_monitor_v2 = ctypes.c_void_p(-4)
        if user32.SetProcessDpiAwarenessContext(awareness_context_per_monitor_v2):
            return "per_monitor_v2"
    except Exception:
        pass

    try:
        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness(2)
        return "per_monitor"
    except Exception:
        pass

    try:
        if user32.SetProcessDPIAware():
            return "system"
    except Exception:
        pass

    return "unchanged"
