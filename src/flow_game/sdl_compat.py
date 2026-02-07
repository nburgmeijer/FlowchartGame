from __future__ import annotations

import ctypes
import os
import tempfile

# Keep PySDL3 quiet and deterministic in offline/packaged environments.
os.environ.setdefault("SDL_DOC_GENERATOR", "0")
os.environ.setdefault("SDL_CHECK_VERSION", "0")
os.environ.setdefault("SDL_CHECK_BINARY_VERSION", "0")
os.environ.setdefault("SDL_DISABLE_METADATA", "1")
os.environ.setdefault("SDL_DOWNLOAD_BINARIES", "1")
os.environ.setdefault("SDL_FIND_BINARIES", "1")
os.environ.setdefault("SDL_LOG_LEVEL", "2")
os.environ.setdefault(
    "SDL_BINARY_PATH", os.path.join(tempfile.gettempdir(), "pysdl3-bin")
)

import sdl3 as _sdl3  # noqa: E402

SDL_Rect = _sdl3.SDL_Rect
SDL_Color = _sdl3.SDL_Color
SDL_Event = _sdl3.SDL_Event
SDL_MouseButtonEvent = _sdl3.SDL_MouseButtonEvent
SDL_MouseMotionEvent = _sdl3.SDL_MouseMotionEvent

SDL_INIT_VIDEO = _sdl3.SDL_INIT_VIDEO
SDL_WINDOWPOS_CENTERED = _sdl3.SDL_WINDOWPOS_CENTERED
SDL_WINDOW_MAXIMIZED = _sdl3.SDL_WINDOW_MAXIMIZED
SDL_WINDOW_RESIZABLE = _sdl3.SDL_WINDOW_RESIZABLE
SDL_WINDOW_HIGH_PIXEL_DENSITY = _sdl3.SDL_WINDOW_HIGH_PIXEL_DENSITY
SDL_WINDOW_SHOWN = 0
SDL_RENDERER_ACCELERATED = 0
SDL_RENDERER_PRESENTVSYNC = 0
SDL_SYSTEM_CURSOR_ARROW = _sdl3.SDL_SYSTEM_CURSOR_DEFAULT
SDL_SYSTEM_CURSOR_HAND = _sdl3.SDL_SYSTEM_CURSOR_POINTER
SDL_QUIT = _sdl3.SDL_EVENT_QUIT
SDL_KEYDOWN = _sdl3.SDL_EVENT_KEY_DOWN
SDL_MOUSEBUTTONDOWN = _sdl3.SDL_EVENT_MOUSE_BUTTON_DOWN
SDL_MOUSEBUTTONUP = _sdl3.SDL_EVENT_MOUSE_BUTTON_UP
SDL_MOUSEMOTION = _sdl3.SDL_EVENT_MOUSE_MOTION
SDL_BUTTON_LEFT = _sdl3.SDL_BUTTON_LEFT
SDL_BUTTON_RIGHT = _sdl3.SDL_BUTTON_RIGHT
SDLK_ESCAPE = _sdl3.SDLK_ESCAPE
SDLK_RETURN = _sdl3.SDLK_RETURN
SDLK_SPACE = _sdl3.SDLK_SPACE
SDLK_DELETE = _sdl3.SDLK_DELETE
SDLK_BACKSPACE = _sdl3.SDLK_BACKSPACE
SDLK_r = _sdl3.SDLK_R
SDLK_x = _sdl3.SDLK_X

SDL_Quit = _sdl3.SDL_Quit
SDL_SetWindowMinimumSize = _sdl3.SDL_SetWindowMinimumSize
SDL_DestroyWindow = _sdl3.SDL_DestroyWindow
SDL_DestroyRenderer = _sdl3.SDL_DestroyRenderer
SDL_DestroyTexture = _sdl3.SDL_DestroyTexture
SDL_CreateTextureFromSurface = _sdl3.SDL_CreateTextureFromSurface
SDL_CreateSystemCursor = _sdl3.SDL_CreateSystemCursor
SDL_SetCursor = _sdl3.SDL_SetCursor
SDL_PollEvent = _sdl3.SDL_PollEvent
SDL_GetDisplayForWindow = _sdl3.SDL_GetDisplayForWindow
SDL_GetDisplayContentScale = _sdl3.SDL_GetDisplayContentScale
SDL_GetWindowDisplayScale = _sdl3.SDL_GetWindowDisplayScale
SDL_GetWindowPixelDensity = _sdl3.SDL_GetWindowPixelDensity
SDL_GetPrimaryDisplay = _sdl3.SDL_GetPrimaryDisplay
SDL_GetDisplayUsableBounds = _sdl3.SDL_GetDisplayUsableBounds
SDL_RenderCoordinatesFromWindow = _sdl3.SDL_RenderCoordinatesFromWindow
SDL_RenderClear = _sdl3.SDL_RenderClear
SDL_RenderPresent = _sdl3.SDL_RenderPresent
SDL_SetRenderDrawColor = _sdl3.SDL_SetRenderDrawColor


def _as_frect(rect: SDL_Rect | None) -> _sdl3.SDL_FRect | None:
    if rect is None:
        return None
    return _sdl3.SDL_FRect(float(rect.x), float(rect.y), float(rect.w), float(rect.h))


def SDL_CreateWindow(
    title: bytes,
    x: int,
    y: int,
    w: int,
    h: int,
    flags: int,
) -> ctypes.c_void_p:
    window = _sdl3.SDL_CreateWindow(title, w, h, flags)
    if window and x != SDL_WINDOWPOS_CENTERED and y != SDL_WINDOWPOS_CENTERED:
        _sdl3.SDL_SetWindowPosition(window, x, y)
    return window


def SDL_CreateRenderer(
    window: ctypes.c_void_p,
    index: int,
    flags: int,
) -> ctypes.c_void_p:
    del index, flags
    return _sdl3.SDL_CreateRenderer(window, None)


def SDL_FreeCursor(cursor: ctypes.c_void_p) -> None:
    _sdl3.SDL_DestroyCursor(cursor)


def SDL_FreeSurface(surface: ctypes.c_void_p) -> None:
    _sdl3.SDL_DestroySurface(surface)


def SDL_GetRendererOutputSize(
    renderer: ctypes.c_void_p,
    w: ctypes._Pointer[ctypes.c_int],
    h: ctypes._Pointer[ctypes.c_int],
) -> bool:
    return _sdl3.SDL_GetCurrentRenderOutputSize(renderer, w, h)


def SDL_GetMouseState(
    x: ctypes._Pointer[ctypes.c_int],
    y: ctypes._Pointer[ctypes.c_int],
) -> int:
    fx = ctypes.c_float()
    fy = ctypes.c_float()
    buttons = _sdl3.SDL_GetMouseState(ctypes.byref(fx), ctypes.byref(fy))
    x_ptr = ctypes.cast(x, ctypes.POINTER(ctypes.c_int))
    y_ptr = ctypes.cast(y, ctypes.POINTER(ctypes.c_int))
    x_ptr[0] = int(round(fx.value))
    y_ptr[0] = int(round(fy.value))
    return int(buttons)


def SDL_RenderCopy(
    renderer: ctypes.c_void_p,
    texture: ctypes.c_void_p,
    src: SDL_Rect | None,
    dst: SDL_Rect | None,
) -> bool:
    src_f = _as_frect(src)
    dst_f = _as_frect(dst)
    src_p = ctypes.byref(src_f) if src_f is not None else None
    dst_p = ctypes.byref(dst_f) if dst_f is not None else None
    return _sdl3.SDL_RenderTexture(renderer, texture, src_p, dst_p)


def SDL_RenderFillRect(renderer: ctypes.c_void_p, rect: SDL_Rect) -> bool:
    frect = _as_frect(rect)
    return _sdl3.SDL_RenderFillRect(renderer, ctypes.byref(frect))


def SDL_RenderDrawRect(renderer: ctypes.c_void_p, rect: SDL_Rect) -> bool:
    frect = _as_frect(rect)
    return _sdl3.SDL_RenderRect(renderer, ctypes.byref(frect))


def SDL_RenderDrawLine(
    renderer: ctypes.c_void_p,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> bool:
    return _sdl3.SDL_RenderLine(
        renderer,
        float(x1),
        float(y1),
        float(x2),
        float(y2),
    )


def SDL_RenderDrawPoint(renderer: ctypes.c_void_p, x: int, y: int) -> bool:
    return _sdl3.SDL_RenderPoint(renderer, float(x), float(y))


def SDL_Init(flags: int) -> int:
    # Preserve SDL2-style semantics expected by the game loop:
    # 0 means success, non-zero means failure.
    return 0 if _sdl3.SDL_Init(flags) else -1


class _TTFCompat:
    @staticmethod
    def TTF_Init() -> int:
        # Preserve SDL2-style semantics expected by the game loop.
        return 0 if _sdl3.TTF_Init() else -1

    TTF_Quit = staticmethod(_sdl3.TTF_Quit)
    TTF_OpenFont = staticmethod(_sdl3.TTF_OpenFont)
    TTF_CloseFont = staticmethod(_sdl3.TTF_CloseFont)

    @staticmethod
    def TTF_RenderUTF8_Blended(
        font: ctypes.c_void_p,
        text: bytes,
        color: SDL_Color,
    ) -> ctypes.c_void_p:
        return _sdl3.TTF_RenderText_Blended(font, text, len(text), color)


sdlttf = _TTFCompat()
