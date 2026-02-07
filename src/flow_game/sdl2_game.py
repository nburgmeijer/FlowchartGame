from __future__ import annotations

import ctypes
import heapq
import os
import sys
from dataclasses import dataclass, field

from .game import DiagramEdge, DiagramNode, FlowLearningGame, Stage


def configure_local_sdl_dll_paths() -> None:
    if os.name != "nt":
        return

    candidates: list[str] = []

    def push(path: str) -> None:
        normalized = os.path.abspath(path)
        if normalized not in candidates and os.path.isdir(normalized):
            candidates.append(normalized)

    env_hint = os.environ.get("PYSDL2_DLL_PATH")
    if env_hint:
        for part in env_hint.split(os.pathsep):
            if part:
                push(part)

    app_root = (
        os.path.dirname(sys.executable)
        if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__))
    )
    push(app_root)
    push(os.path.join(app_root, "lib"))
    push(os.path.join(app_root, "dll"))
    push(os.path.join(app_root, "sdl2"))
    push(os.path.join(app_root, "sdl2dll"))

    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        push(meipass)
        push(os.path.join(meipass, "lib"))
        push(os.path.join(meipass, "dll"))
        push(os.path.join(meipass, "sdl2"))
        push(os.path.join(meipass, "sdl2dll"))

    runtime_candidates = gather_sdl_dll_dirs(candidates)
    if not runtime_candidates:
        return

    # Point PySDL2 to app-local copies first.
    os.environ["PYSDL2_DLL_PATH"] = os.pathsep.join(runtime_candidates)

    # Also register directories with Windows loader for direct ctypes loading.
    current_path = os.environ.get("PATH", "")
    for dll_dir in runtime_candidates:
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(dll_dir)
            except OSError:
                pass
        if dll_dir not in current_path.split(os.pathsep):
            current_path = (
                f"{dll_dir}{os.pathsep}{current_path}"
                if current_path
                else dll_dir
            )
    os.environ["PATH"] = current_path


def has_sdl_dll(path: str) -> bool:
    try:
        names = os.listdir(path)
    except OSError:
        return False
    lowered = [name.lower() for name in names]
    return any(name.startswith("sdl2") and name.endswith(".dll") for name in lowered)


def gather_sdl_dll_dirs(base_dirs: list[str]) -> list[str]:
    found: list[str] = []

    def push(path: str) -> None:
        normalized = os.path.abspath(path)
        if normalized not in found and os.path.isdir(normalized):
            found.append(normalized)

    for base in base_dirs:
        if has_sdl_dll(base):
            push(base)
        # PyInstaller onefile often extracts SDL DLLs into nested folders
        # such as "sdl2dll/dll", so discover real DLL parent dirs recursively.
        try:
            for root, _, files in os.walk(base):
                lowered = [name.lower() for name in files]
                if any(
                    name.startswith("sdl2") and name.endswith(".dll")
                    for name in lowered
                ):
                    push(root)
        except OSError:
            continue
    return found


configure_local_sdl_dll_paths()

try:
    import sdl2
    from sdl2 import sdlttf
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    sdl2 = None  # type: ignore[assignment]
    sdlttf = None  # type: ignore[assignment]
    SDL_IMPORT_ERROR: ModuleNotFoundError | None = exc
else:
    SDL_IMPORT_ERROR = None

WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
MIN_WINDOW_WIDTH = 1200
MIN_WINDOW_HEIGHT = 760
VIEW_WIDTH = WINDOW_WIDTH
VIEW_HEIGHT = WINDOW_HEIGHT
SIDEBAR_WIDTH = 390
HEADER_HEIGHT = 170
CANVAS_MARGIN = 20
GRID_SIZE = 22

PROCESS_BLOCK_W_UNITS = 6
PROCESS_BLOCK_H_UNITS = 3
DECISION_BLOCK_W_UNITS = 6
DECISION_BLOCK_H_UNITS = 4

MAX_BLOCK_LABEL_SIZE = 20
MIN_BLOCK_LABEL_SIZE = 10

BG_COLOR = (11, 13, 17, 255)
GRID_MINOR = (29, 34, 44, 255)
GRID_MAJOR = (46, 52, 68, 255)
PANEL_COLOR = (17, 20, 26, 255)
PANEL_BORDER = (66, 72, 88, 255)
TEXT_COLOR = (230, 233, 238, 255)
SUBTEXT_COLOR = (165, 173, 189, 255)
ACCENT = (110, 193, 255, 255)
ERROR_COLOR = (255, 123, 120, 255)
SUCCESS_COLOR = (123, 233, 170, 255)
NODE_FILL = (8, 10, 13, 255)
NODE_BORDER = (224, 228, 236, 255)
EDGE_COLOR = (238, 241, 248, 255)
HANDLE_COLOR = (60, 196, 255, 255)
HANDLE_ACTIVE = (255, 175, 62, 255)
HANDLE_RADIUS = 8
HANDLE_HIT_RADIUS = 14
ARROW_HEAD_LENGTH = 10
MIN_CONNECTOR_SEGMENT = ARROW_HEAD_LENGTH * 2
MIN_START_STEM = GRID_SIZE // 2
MIN_END_SEGMENT = GRID_SIZE // 2
MIN_END_STUB_FALLBACK = max(1, MIN_END_SEGMENT // 2)
MAX_VISIBLE_MESSAGES = 5
MIN_BLOCK_GAP = 2 * GRID_SIZE
DIAGONAL_BLOCK_GAP = GRID_SIZE
CONNECTOR_OBJECT_CLEARANCE = GRID_SIZE
PATHFINDING_TURN_PENALTIES = (0,)
PATHFINDING_MAX_EXPANDED = 1800
PREVIEW_PATHFINDING_TURN_PENALTIES = (0,)
PREVIEW_PATHFINDING_MAX_EXPANDED = 900


@dataclass
class PlacedNode:
    template: DiagramNode
    x: int
    y: int

    @property
    def size(self) -> tuple[int, int]:
        if self.template.block_type.value == "decision":
            return (
                DECISION_BLOCK_W_UNITS * GRID_SIZE,
                DECISION_BLOCK_H_UNITS * GRID_SIZE,
            )
        return (
            PROCESS_BLOCK_W_UNITS * GRID_SIZE,
            PROCESS_BLOCK_H_UNITS * GRID_SIZE,
        )

    @property
    def rect(self) -> sdl2.SDL_Rect:
        width, height = self.size
        return sdl2.SDL_Rect(self.x, self.y, width, height)

    @property
    def center(self) -> tuple[int, int]:
        width, height = self.size
        return (self.x + width // 2, self.y + height // 2)


@dataclass
class BuiltEdge:
    source: str
    target: str
    label: str
    source_anchor: int
    target_anchor: int


@dataclass
class BuilderState:
    placed_nodes: dict[str, PlacedNode] = field(default_factory=dict)
    edges: list[BuiltEdge] = field(default_factory=list)
    selected_template: str | None = None
    edge_mode: bool = False
    edge_source: str | None = None
    drag_node: str | None = None
    drag_offset: tuple[int, int] = (0, 0)
    messages: list[tuple[str, tuple[int, int, int, int]]] = field(default_factory=list)
    modal: ValidationModal | None = None
    last_cleared_stage_index: int | None = None
    selected_node: str | None = None
    hovered_connector: tuple[str, int] | None = None
    drag_connector_source: tuple[str, int] | None = None
    drag_target_connector: tuple[str, int] | None = None
    drag_mouse_pos: tuple[int, int] | None = None
    selected_edge_index: int | None = None
    drag_original_pos: tuple[int, int] | None = None
    drag_position_invalid: bool = False
    placement_pos: tuple[int, int] | None = None
    placement_invalid: bool = False

    def reset_for_stage(self) -> None:
        self.placed_nodes.clear()
        self.edges.clear()
        self.selected_template = None
        self.edge_mode = False
        self.edge_source = None
        self.drag_node = None
        self.drag_offset = (0, 0)
        self.messages.clear()
        self.modal = None
        self.selected_node = None
        self.hovered_connector = None
        self.drag_connector_source = None
        self.drag_target_connector = None
        self.drag_mouse_pos = None
        self.selected_edge_index = None
        self.drag_original_pos = None
        self.drag_position_invalid = False
        self.placement_pos = None
        self.placement_invalid = False

    def push_message(self, text: str, color: tuple[int, int, int, int]) -> None:
        self.messages.append((text, color))
        self.messages = self.messages[-6:]


@dataclass(frozen=True)
class ModalButton:
    label: str
    action: str


@dataclass
class ValidationModal:
    title: str
    lines: list[str]
    color: tuple[int, int, int, int]
    buttons: list[ModalButton]


@dataclass
class TextCacheEntry:
    texture: ctypes.c_void_p
    width: int
    height: int


class TextRenderer:
    def __init__(self, renderer: ctypes.c_void_p, font_path: str) -> None:
        self.renderer = renderer
        self.fonts: dict[int, ctypes.c_void_p] = {}
        self.cache: dict[
            tuple[str, int, tuple[int, int, int, int]],
            TextCacheEntry,
        ] = {}
        self.font_path = font_path

    def destroy(self) -> None:
        for entry in self.cache.values():
            sdl2.SDL_DestroyTexture(entry.texture)
        self.cache.clear()

        for font in self.fonts.values():
            sdlttf.TTF_CloseFont(font)
        self.fonts.clear()

    def draw(
        self,
        text: str,
        x: int,
        y: int,
        color: tuple[int, int, int, int] = TEXT_COLOR,
        size: int = 18,
    ) -> None:
        entry = self._entry(text=text, size=size, color=color)
        rect = sdl2.SDL_Rect(x, y, entry.width, entry.height)
        sdl2.SDL_RenderCopy(self.renderer, entry.texture, None, rect)

    def text_size(
        self,
        text: str,
        size: int,
        color: tuple[int, int, int, int] = TEXT_COLOR,
    ) -> tuple[int, int]:
        entry = self._entry(text=text, size=size, color=color)
        return (entry.width, entry.height)

    def wrap_draw(
        self,
        text: str,
        x: int,
        y: int,
        width: int,
        color: tuple[int, int, int, int] = TEXT_COLOR,
        size: int = 18,
        line_gap: int = 4,
    ) -> int:
        lines = wrap_text(text=text, max_chars=max(20, width // max(7, size // 2 + 2)))
        cursor_y = y
        for line in lines:
            self.draw(line, x, cursor_y, color=color, size=size)
            cursor_y += size + line_gap
        return cursor_y

    def _font(self, size: int) -> ctypes.c_void_p:
        if size not in self.fonts:
            font = sdlttf.TTF_OpenFont(self.font_path.encode("utf-8"), size)
            if not font:
                raise RuntimeError("Unable to open font for text rendering.")
            self.fonts[size] = font
        return self.fonts[size]

    def _entry(
        self,
        text: str,
        size: int,
        color: tuple[int, int, int, int],
    ) -> TextCacheEntry:
        key = (text, size, color)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        font = self._font(size)
        sdl_color = sdl2.SDL_Color(*color)
        surface = sdlttf.TTF_RenderUTF8_Blended(font, text.encode("utf-8"), sdl_color)
        if not surface:
            raise RuntimeError(f"Failed to render text: {text}")

        texture = sdl2.SDL_CreateTextureFromSurface(self.renderer, surface)
        if not texture:
            sdl2.SDL_FreeSurface(surface)
            raise RuntimeError("Failed to create text texture.")

        width = surface.contents.w
        height = surface.contents.h
        sdl2.SDL_FreeSurface(surface)

        entry = TextCacheEntry(texture=texture, width=width, height=height)
        self.cache[key] = entry
        return entry


def main() -> None:
    if SDL_IMPORT_ERROR is not None:
        raise RuntimeError(
            "SDL2 Python bindings are missing. Install with "
            "`pip install -e .[dev]` (or `pip install PySDL2`) and ensure "
            "native SDL2/SDL2_ttf libraries are installed."
        ) from SDL_IMPORT_ERROR

    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        raise RuntimeError("SDL2 video initialization failed.")

    if sdlttf.TTF_Init() != 0:
        sdl2.SDL_Quit()
        raise RuntimeError("SDL2_ttf initialization failed.")

    window = sdl2.SDL_CreateWindow(
        b"Flow Diagram Learning Game",
        sdl2.SDL_WINDOWPOS_CENTERED,
        sdl2.SDL_WINDOWPOS_CENTERED,
        WINDOW_WIDTH,
        WINDOW_HEIGHT,
        sdl2.SDL_WINDOW_SHOWN | sdl2.SDL_WINDOW_MAXIMIZED | sdl2.SDL_WINDOW_RESIZABLE,
    )
    if not window:
        sdlttf.TTF_Quit()
        sdl2.SDL_Quit()
        raise RuntimeError("Could not create SDL2 window.")
    sdl2.SDL_SetWindowMinimumSize(window, MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

    renderer = sdl2.SDL_CreateRenderer(
        window,
        -1,
        sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC,
    )
    if not renderer:
        sdl2.SDL_DestroyWindow(window)
        sdlttf.TTF_Quit()
        sdl2.SDL_Quit()
        raise RuntimeError("Could not create SDL2 renderer.")

    font_path = find_font_path()
    if font_path is None:
        sdl2.SDL_DestroyRenderer(renderer)
        sdl2.SDL_DestroyWindow(window)
        sdlttf.TTF_Quit()
        sdl2.SDL_Quit()
        raise RuntimeError(
            "No readable TTF font found. Install a system font like DejaVuSans."
        )

    text = TextRenderer(renderer=renderer, font_path=font_path)

    try:
        run_loop(renderer=renderer, text=text)
    finally:
        text.destroy()
        sdl2.SDL_DestroyRenderer(renderer)
        sdl2.SDL_DestroyWindow(window)
        sdlttf.TTF_Quit()
        sdl2.SDL_Quit()


def run_loop(renderer: ctypes.c_void_p, text: TextRenderer) -> None:
    game = FlowLearningGame()
    builder = BuilderState()
    arrow_cursor = sdl2.SDL_CreateSystemCursor(sdl2.SDL_SYSTEM_CURSOR_ARROW)
    hand_cursor = sdl2.SDL_CreateSystemCursor(sdl2.SDL_SYSTEM_CURSOR_HAND)

    if arrow_cursor:
        sdl2.SDL_SetCursor(arrow_cursor)

    running = True
    event = sdl2.SDL_Event()

    try:
        while running:
            update_layout_size(renderer)
            while sdl2.SDL_PollEvent(ctypes.byref(event)):
                event_type = event.type

                if event_type == sdl2.SDL_QUIT:
                    running = False
                elif event_type == sdl2.SDL_KEYDOWN:
                    running = handle_keydown(
                        game=game,
                        builder=builder,
                        key=event.key.keysym.sym,
                    )
                elif event_type == sdl2.SDL_MOUSEBUTTONDOWN:
                    handle_mouse_down(game=game, builder=builder, event=event.button)
                elif event_type == sdl2.SDL_MOUSEBUTTONUP:
                    handle_mouse_up(builder=builder, event=event.button)
                elif event_type == sdl2.SDL_MOUSEMOTION:
                    handle_mouse_motion(game=game, builder=builder, event=event.motion)

            update_cursor_icon(
                game=game,
                builder=builder,
                arrow_cursor=arrow_cursor,
                hand_cursor=hand_cursor,
            )
            draw_frame(renderer=renderer, text=text, game=game, builder=builder)
    finally:
        if hand_cursor:
            sdl2.SDL_FreeCursor(hand_cursor)
        if arrow_cursor:
            sdl2.SDL_FreeCursor(arrow_cursor)


def update_cursor_icon(
    game: FlowLearningGame,
    builder: BuilderState,
    arrow_cursor: ctypes.c_void_p,
    hand_cursor: ctypes.c_void_p,
) -> None:
    mouse_x = ctypes.c_int(0)
    mouse_y = ctypes.c_int(0)
    sdl2.SDL_GetMouseState(ctypes.byref(mouse_x), ctypes.byref(mouse_y))
    is_selectable = is_hovering_selectable(
        game=game,
        builder=builder,
        x=mouse_x.value,
        y=mouse_y.value,
    )
    if is_selectable and hand_cursor:
        sdl2.SDL_SetCursor(hand_cursor)
    elif arrow_cursor:
        sdl2.SDL_SetCursor(arrow_cursor)


def update_layout_size(renderer: ctypes.c_void_p) -> None:
    global VIEW_WIDTH, VIEW_HEIGHT
    width = ctypes.c_int(0)
    height = ctypes.c_int(0)
    sdl2.SDL_GetRendererOutputSize(renderer, ctypes.byref(width), ctypes.byref(height))
    if width.value > 0 and height.value > 0:
        VIEW_WIDTH = width.value
        VIEW_HEIGHT = height.value


def current_width() -> int:
    return VIEW_WIDTH


def current_height() -> int:
    return VIEW_HEIGHT


def is_hovering_selectable(
    game: FlowLearningGame,
    builder: BuilderState,
    x: int,
    y: int,
) -> bool:
    if builder.modal is not None:
        return modal_action_at_point(modal=builder.modal, x=x, y=y) is not None

    if game.is_completed():
        return False

    stage = game.current_stage()
    if find_template_click(stage=stage, x=x, y=y) is not None:
        return True
    if builder.selected_template is not None and point_in_rect(x, y, canvas_rect()):
        return True
    if find_node_hit(builder=builder, x=x, y=y) is not None:
        return True
    if find_edge_hit(builder=builder, stage=stage, x=x, y=y) is not None:
        return True
    if (
        builder.selected_node is not None
        and find_connector_in_square_hitbox(
            builder=builder,
            x=x,
            y=y,
            node_id=builder.selected_node,
        )
        is not None
    ):
        return True
    return False


def handle_keydown(game: FlowLearningGame, builder: BuilderState, key: int) -> bool:
    if key == sdl2.SDLK_ESCAPE and builder.selected_template is not None:
        cancel_template_placement(builder)
        builder.push_message("Block placement canceled.", SUBTEXT_COLOR)
        return True

    if key == sdl2.SDLK_ESCAPE:
        return False

    if builder.modal is not None:
        if key in (sdl2.SDLK_RETURN, sdl2.SDLK_SPACE):
            default_action = (
                builder.modal.buttons[0].action
                if builder.modal.buttons
                else "close_modal"
            )
            handle_modal_action(game=game, builder=builder, action=default_action)
        return True

    if game.is_completed():
        if key == sdl2.SDLK_r:
            game.current_stage_index = 0
            game.badges.clear()
            game.attempts_by_stage.clear()
            builder.reset_for_stage()
            builder.push_message("Game reset.", SUBTEXT_COLOR)
        return True

    if key == sdl2.SDLK_RETURN:
        submit_stage(game=game, builder=builder)
        return True

    if key == sdl2.SDLK_x:
        if builder.edges:
            removed_index = len(builder.edges) - 1
            builder.edges.pop()
            if builder.selected_edge_index == removed_index:
                builder.selected_edge_index = None
            elif (
                builder.selected_edge_index is not None
                and builder.selected_edge_index > removed_index
            ):
                builder.selected_edge_index -= 1
            builder.push_message("Last edge removed.", SUBTEXT_COLOR)
        return True

    if key in (sdl2.SDLK_DELETE, sdl2.SDLK_BACKSPACE):
        if (
            builder.selected_edge_index is not None
            and 0 <= builder.selected_edge_index < len(builder.edges)
        ):
            del builder.edges[builder.selected_edge_index]
            builder.push_message("Selected connector removed.", SUBTEXT_COLOR)
            builder.selected_edge_index = None
            return True
        if builder.selected_node is not None:
            remove_node(builder=builder, node_id=builder.selected_node)
        return True

    if key == sdl2.SDLK_r:
        builder.reset_for_stage()
        builder.push_message("Stage workspace cleared.", SUBTEXT_COLOR)
        return True

    return True


def handle_mouse_down(
    game: FlowLearningGame,
    builder: BuilderState,
    event: sdl2.SDL_MouseButtonEvent,
) -> None:
    mouse_x = int(event.x)
    mouse_y = int(event.y)

    if builder.modal is not None:
        if event.button == sdl2.SDL_BUTTON_LEFT:
            action = modal_action_at_point(modal=builder.modal, x=mouse_x, y=mouse_y)
            if action is not None:
                handle_modal_action(game=game, builder=builder, action=action)
        return

    if game.is_completed():
        return

    stage = game.current_stage()

    if event.button == sdl2.SDL_BUTTON_LEFT:
        if builder.drag_connector_source is not None:
            complete_drag_connector_if_possible(game=game, builder=builder)
            return

        template_id = find_template_click(stage=stage, x=mouse_x, y=mouse_y)
        if template_id is not None:
            builder.selected_template = template_id
            builder.selected_node = None
            builder.hovered_connector = None
            builder.selected_edge_index = None
            builder.drag_connector_source = None
            builder.drag_target_connector = None
            builder.drag_mouse_pos = None
            builder.placement_pos = None
            builder.placement_invalid = False
            update_template_placement_preview(
                game=game,
                builder=builder,
                stage=stage,
                x=mouse_x,
                y=mouse_y,
            )
            builder.push_message(
                f"Selected {template_id}. Click canvas to place.",
                SUBTEXT_COLOR,
            )
            return

        if builder.selected_template is not None:
            if point_in_rect(mouse_x, mouse_y, canvas_rect()):
                try_place_selected_template(
                    game=game,
                    builder=builder,
                    x=mouse_x,
                    y=mouse_y,
                )
            return

        if builder.selected_node is not None:
            update_hovered_connector(builder=builder, x=mouse_x, y=mouse_y)

        if builder.hovered_connector is not None:
            builder.drag_connector_source = builder.hovered_connector
            builder.drag_mouse_pos = (mouse_x, mouse_y)
            builder.drag_target_connector = None
            builder.selected_edge_index = None
            builder.push_message("Drag connector to another block.", SUBTEXT_COLOR)
            return

        hit_node = find_node_hit(builder=builder, x=mouse_x, y=mouse_y)
        if hit_node is not None:
            builder.selected_node = hit_node
            builder.selected_edge_index = None

            if (
                builder.hovered_connector is not None
                and builder.hovered_connector[0] == hit_node
            ):
                builder.drag_connector_source = builder.hovered_connector
                builder.drag_mouse_pos = (mouse_x, mouse_y)
                builder.drag_target_connector = None
                builder.push_message("Drag connector to another block.", SUBTEXT_COLOR)
                return

            placed = builder.placed_nodes[hit_node]
            builder.drag_node = hit_node
            builder.drag_offset = (mouse_x - placed.x, mouse_y - placed.y)
            builder.drag_original_pos = (placed.x, placed.y)
            builder.drag_position_invalid = False
            return

        edge_index = find_edge_hit(builder=builder, stage=stage, x=mouse_x, y=mouse_y)
        if edge_index is not None:
            builder.selected_edge_index = edge_index
            builder.selected_node = None
            builder.hovered_connector = None
            builder.push_message("Connector selected.", SUBTEXT_COLOR)
            return

        builder.selected_node = None
        builder.hovered_connector = None
        builder.selected_edge_index = None

    if event.button == sdl2.SDL_BUTTON_RIGHT:
        if builder.selected_template is not None:
            cancel_template_placement(builder)
            builder.push_message("Block placement canceled.", SUBTEXT_COLOR)
            return
        hit_node = find_node_hit(builder=builder, x=mouse_x, y=mouse_y)
        if hit_node is not None:
            remove_node(builder=builder, node_id=hit_node)


def handle_mouse_up(builder: BuilderState, event: sdl2.SDL_MouseButtonEvent) -> None:
    if event.button == sdl2.SDL_BUTTON_LEFT:
        if builder.drag_node is not None and builder.drag_position_invalid:
            node = builder.placed_nodes.get(builder.drag_node)
            if node is not None and builder.drag_original_pos is not None:
                node.x, node.y = builder.drag_original_pos
                builder.push_message(
                    "Cannot place block: keep block spacing and valid routes.",
                    ERROR_COLOR,
                )
        builder.drag_original_pos = None
        builder.drag_position_invalid = False
        builder.drag_node = None


def handle_mouse_motion(
    game: FlowLearningGame,
    builder: BuilderState,
    event: sdl2.SDL_MouseMotionEvent,
) -> None:
    if game.is_completed():
        return

    if builder.modal is not None:
        return

    mouse_x = int(event.x)
    mouse_y = int(event.y)

    if builder.selected_template is not None:
        stage = game.current_stage()
        update_template_placement_preview(
            game=game,
            builder=builder,
            stage=stage,
            x=mouse_x,
            y=mouse_y,
        )
        return

    if builder.drag_connector_source is not None:
        builder.drag_mouse_pos = (mouse_x, mouse_y)
        source_node_id, _ = builder.drag_connector_source
        builder.drag_target_connector = find_nearest_connector(
            builder=builder,
            x=mouse_x,
            y=mouse_y,
            exclude_node_id=source_node_id,
        )
        return

    if builder.drag_node is None:
        update_hovered_connector(builder=builder, x=mouse_x, y=mouse_y)
        return

    stage = game.current_stage()
    node = builder.placed_nodes[builder.drag_node]
    offset_x, offset_y = builder.drag_offset

    width, height = node.size
    target_x = mouse_x - offset_x
    target_y = mouse_y - offset_y
    node.x, node.y = clamp_node_position(
        stage=stage,
        node=node,
        x=target_x,
        y=target_y,
        width=width,
        height=height,
    )
    builder.drag_position_invalid = not is_valid_drag_position(
        builder=builder,
        stage=stage,
        moving_node_id=builder.drag_node,
    )
    update_hovered_connector(builder=builder, x=mouse_x, y=mouse_y)


def place_selected_node(
    game: FlowLearningGame,
    builder: BuilderState,
    x: int,
    y: int,
) -> None:
    stage = game.current_stage()
    template_id = builder.selected_template
    if template_id is None:
        return

    if template_id in builder.placed_nodes:
        builder.push_message(f"{template_id} is already placed.", ERROR_COLOR)
        return

    template = next(
        node for node in stage.expected_nodes if node.node_id == template_id
    )
    node = PlacedNode(template=template, x=0, y=0)
    width, height = node.size

    target_x = x - width // 2
    target_y = y - height // 2
    node.x, node.y = clamp_node_position(
        stage=stage,
        node=node,
        x=target_x,
        y=target_y,
        width=width,
        height=height,
    )

    builder.placed_nodes[template_id] = node
    builder.selected_node = None
    builder.hovered_connector = None
    builder.selected_template = None
    builder.placement_pos = None
    builder.placement_invalid = False
    builder.push_message(f"Placed {template_id}.", SUBTEXT_COLOR)


def update_template_placement_preview(
    game: FlowLearningGame,
    builder: BuilderState,
    stage: Stage,
    x: int,
    y: int,
) -> None:
    template_id = builder.selected_template
    if template_id is None:
        builder.placement_pos = None
        builder.placement_invalid = False
        return

    template = next(
        node for node in stage.expected_nodes if node.node_id == template_id
    )
    probe = PlacedNode(template=template, x=0, y=0)
    width, height = probe.size
    target_x = x - width // 2
    target_y = y - height // 2
    clamped_x, clamped_y = clamp_node_position(
        stage=stage,
        node=probe,
        x=target_x,
        y=target_y,
        width=width,
        height=height,
    )
    builder.placement_pos = (clamped_x, clamped_y)
    builder.placement_invalid = not can_place_template_at(
        builder=builder,
        template=template,
        x=clamped_x,
        y=clamped_y,
    )


def try_place_selected_template(
    game: FlowLearningGame,
    builder: BuilderState,
    x: int,
    y: int,
) -> None:
    stage = game.current_stage()
    update_template_placement_preview(
        game=game,
        builder=builder,
        stage=stage,
        x=x,
        y=y,
    )
    if builder.placement_pos is None:
        return
    if builder.placement_invalid:
        builder.push_message(
            "Cannot place block: keep minimum distance from other blocks.",
            ERROR_COLOR,
        )
        return
    place_selected_node(
        game=game,
        builder=builder,
        x=x,
        y=y,
    )


def cancel_template_placement(builder: BuilderState) -> None:
    builder.selected_template = None
    builder.placement_pos = None
    builder.placement_invalid = False


def remove_node(builder: BuilderState, node_id: str) -> None:
    if node_id not in builder.placed_nodes:
        return

    del builder.placed_nodes[node_id]
    remaining_edges = [
        edge
        for edge in builder.edges
        if edge.source != node_id and edge.target != node_id
    ]
    builder.edges = remaining_edges
    builder.selected_edge_index = None
    builder.push_message(f"Removed {node_id} and connected edges.", SUBTEXT_COLOR)
    if builder.selected_node == node_id:
        builder.selected_node = None
        builder.hovered_connector = None


def submit_stage(game: FlowLearningGame, builder: BuilderState) -> None:
    if game.is_completed():
        return

    if builder.modal is not None:
        return

    stage = game.current_stage()
    stage_index_before_submit = game.current_stage_index
    nodes_to_submit: list[DiagramNode] = []

    for placed in builder.placed_nodes.values():
        lane = placed.template.lane
        if stage.lanes:
            lane = lane_from_position(
                stage=stage,
                y=placed.center[1],
                rect=canvas_rect(),
            )

        nodes_to_submit.append(
            DiagramNode(
                node_id=placed.template.node_id,
                block_type=placed.template.block_type,
                label=placed.template.label,
                lane=lane,
            )
        )

    result = game.submit_current_stage(
        nodes=tuple(nodes_to_submit),
        edges=tuple(
            DiagramEdge(source=edge.source, target=edge.target, label=edge.label)
            for edge in builder.edges
        ),
    )

    if result.passed:
        lines = [
            f"{stage.title} cleared.",
            "Stage validation succeeded.",
        ]
        if result.earned_badges:
            lines.append("Awarded badges:")
            lines.extend(f"- {badge}" for badge in result.earned_badges)
        else:
            lines.append("No new badge on this clear.")
        if result.game_completed:
            lines.append("All stages complete.")

        builder.last_cleared_stage_index = stage_index_before_submit
        builder.modal = ValidationModal(
            title="Stage Cleared",
            lines=lines,
            color=SUCCESS_COLOR,
            buttons=[
                ModalButton(label="Retry Stage", action="retry_stage"),
                ModalButton(label="Next Stage", action="next_stage"),
            ],
        )
    else:
        attempt_count = game.attempts_by_stage.get(stage.stage_id, 0)
        lines = [
            "Stage validation failed.",
            *list(result.errors[:4]),
        ]
        if attempt_count >= 3:
            lines.append(f"Hint: {stage.hint}")
        lines.append(f"Attempts on this stage: {attempt_count}")
        builder.modal = ValidationModal(
            title="Validation Result",
            lines=lines,
            color=ERROR_COLOR,
            buttons=[ModalButton(label="Continue Editing", action="close_modal")],
        )


def find_template_click(stage: Stage, x: int, y: int) -> str | None:
    for index, node in enumerate(stage.expected_nodes):
        item_rect = template_item_rect(index)
        if point_in_rect(x, y, item_rect):
            return node.node_id
    return None


def find_node_hit(builder: BuilderState, x: int, y: int) -> str | None:
    for node_id in reversed(list(builder.placed_nodes.keys())):
        placed = builder.placed_nodes[node_id]
        rect = placed.rect
        if placed.template.block_type.value == "decision":
            if point_in_diamond(x=x, y=y, rect=rect):
                return node_id
            continue
        if point_in_rect(x, y, rect):
            return node_id
    return None


def find_edge_hit(
    builder: BuilderState,
    stage: Stage,
    x: int,
    y: int,
) -> int | None:
    routed_edges = route_all_edge_paths(builder=builder, stage=stage)
    threshold = 6
    for edge, path in reversed(routed_edges):
        if len(path) < 2:
            continue
        edge_index = builder.edges.index(edge)
        for idx in range(len(path) - 1):
            sx, sy = path[idx]
            tx, ty = path[idx + 1]
            if point_near_orthogonal_segment(x, y, sx, sy, tx, ty, threshold):
                return edge_index
    return None


def point_near_orthogonal_segment(
    px: int,
    py: int,
    sx: int,
    sy: int,
    tx: int,
    ty: int,
    threshold: int,
) -> bool:
    if sx == tx:
        if abs(px - sx) > threshold:
            return False
        return min(sy, ty) - threshold <= py <= max(sy, ty) + threshold
    if sy == ty:
        if abs(py - sy) > threshold:
            return False
        return min(sx, tx) - threshold <= px <= max(sx, tx) + threshold
    return False


def update_hovered_connector(builder: BuilderState, x: int, y: int) -> None:
    if builder.selected_node is None:
        builder.hovered_connector = None
        return

    nearest = find_connector_in_square_hitbox(
        builder=builder,
        x=x,
        y=y,
        node_id=builder.selected_node,
    )
    builder.hovered_connector = nearest


def find_connector_in_square_hitbox(
    builder: BuilderState,
    x: int,
    y: int,
    node_id: str,
) -> tuple[str, int] | None:
    placed = builder.placed_nodes.get(node_id)
    if placed is None:
        return None

    points = connector_points(placed)
    for idx, (px, py) in enumerate(points):
        is_highlighted = (
            builder.hovered_connector == (node_id, idx)
            or builder.drag_connector_source == (node_id, idx)
            or builder.drag_target_connector == (node_id, idx)
        )
        hit_radius = HANDLE_RADIUS + (2 if is_highlighted else 0)
        if abs(x - px) <= hit_radius and abs(y - py) <= hit_radius:
            return (node_id, idx)
    return None


def complete_drag_connector_if_possible(
    game: FlowLearningGame,
    builder: BuilderState,
) -> None:
    if builder.drag_connector_source is None:
        return

    source_node_id, source_anchor = builder.drag_connector_source
    target = builder.drag_target_connector

    if target is None:
        builder.drag_connector_source = None
        builder.drag_target_connector = None
        builder.drag_mouse_pos = None
        builder.push_message("Connector cancelled.", SUBTEXT_COLOR)
        return

    target_node_id, target_anchor = target
    if target_node_id == source_node_id:
        builder.drag_connector_source = None
        builder.drag_target_connector = None
        builder.drag_mouse_pos = None
        builder.push_message("Cannot connect a block to itself.", ERROR_COLOR)
        return

    stage = game.current_stage()
    expected_label = ""
    for edge in stage.expected_edges:
        if edge.source == source_node_id and edge.target == target_node_id:
            expected_label = edge.label
            break

    if any(
        edge.source == source_node_id and edge.target == target_node_id
        for edge in builder.edges
    ):
        builder.push_message("Edge already exists.", ERROR_COLOR)
    else:
        candidate = BuiltEdge(
            source=source_node_id,
            target=target_node_id,
            label=expected_label,
            source_anchor=source_anchor,
            target_anchor=target_anchor,
        )
        temp_edges = [*builder.edges, candidate]
        routed = route_all_edge_paths(builder=builder, stage=stage, edges=temp_edges)
        if not any(edge is candidate and len(path) > 1 for edge, path in routed):
            builder.push_message("No valid path without crossing.", ERROR_COLOR)
        else:
            builder.edges.append(candidate)
            builder.push_message(
                f"Edge added: {source_node_id} -> {target_node_id}",
                SUBTEXT_COLOR,
            )

    builder.drag_connector_source = None
    builder.drag_target_connector = None
    builder.drag_mouse_pos = None


def connector_points(placed: PlacedNode) -> list[tuple[int, int]]:
    rect = placed.rect
    cx, cy = placed.center

    if placed.template.block_type.value == "decision":
        return [
            (cx, rect.y),
            (rect.x + rect.w, cy),
            (cx, rect.y + rect.h),
            (rect.x, cy),
        ]

    return [
        (cx, rect.y),
        (rect.x + rect.w, cy),
        (cx, rect.y + rect.h),
        (rect.x, cy),
    ]


def find_nearest_connector(
    builder: BuilderState,
    x: int,
    y: int,
    exclude_node_id: str | None = None,
    include_only_node: str | None = None,
) -> tuple[str, int] | None:
    closest: tuple[str, int] | None = None
    closest_dist_sq = HANDLE_HIT_RADIUS * HANDLE_HIT_RADIUS

    for node_id, placed in builder.placed_nodes.items():
        if exclude_node_id is not None and node_id == exclude_node_id:
            continue
        if include_only_node is not None and node_id != include_only_node:
            continue

        points = connector_points(placed)
        for idx, (px, py) in enumerate(points):
            dx = x - px
            dy = y - py
            dist_sq = dx * dx + dy * dy
            if dist_sq <= closest_dist_sq:
                closest = (node_id, idx)
                closest_dist_sq = dist_sq

    return closest


def draw_frame(
    renderer: ctypes.c_void_p,
    text: TextRenderer,
    game: FlowLearningGame,
    builder: BuilderState,
) -> None:
    set_color(renderer, BG_COLOR)
    sdl2.SDL_RenderClear(renderer)

    draw_grid(renderer=renderer)
    draw_sidebar(renderer=renderer)
    draw_header(renderer=renderer)

    if game.is_completed() and builder.modal is None:
        draw_complete_screen(renderer=renderer, text=text, game=game)
        sdl2.SDL_RenderPresent(renderer)
        return

    stage = game.current_stage() if not game.is_completed() else None

    if stage is not None:
        draw_stage_text(text=text, stage=stage)
        draw_controls(text=text, builder=builder)
        draw_template_list(text=text, stage=stage, builder=builder)

        if stage.lanes:
            draw_swimlanes(renderer=renderer, text=text, stage=stage)

        draw_edges(renderer=renderer, text=text, builder=builder, stage=stage)
        draw_drag_connector_preview(
            renderer=renderer,
            builder=builder,
            stage=stage,
        )
        draw_template_placement_preview(renderer=renderer, builder=builder, stage=stage)
        draw_nodes(renderer=renderer, text=text, builder=builder)
        draw_connector_handles(renderer=renderer, builder=builder)
        draw_messages(text=text, builder=builder)
    else:
        draw_complete_screen(renderer=renderer, text=text, game=game)
    if builder.modal is not None:
        draw_validation_modal(renderer=renderer, text=text, modal=builder.modal)

    sdl2.SDL_RenderPresent(renderer)


def handle_modal_action(
    game: FlowLearningGame,
    builder: BuilderState,
    action: str,
) -> None:
    if action == "close_modal":
        builder.modal = None
        return

    if action == "retry_stage":
        if builder.last_cleared_stage_index is not None:
            game.current_stage_index = builder.last_cleared_stage_index
        builder.reset_for_stage()
        builder.push_message("Retrying cleared stage.", SUBTEXT_COLOR)
        return

    if action == "next_stage":
        builder.reset_for_stage()
        if game.is_completed():
            builder.push_message("All stages complete.", SUCCESS_COLOR)
        else:
            builder.push_message("Moved to next stage.", SUBTEXT_COLOR)


def modal_action_at_point(modal: ValidationModal, x: int, y: int) -> str | None:
    for rect, button in modal_button_layout(modal):
        if point_in_rect(x, y, rect):
            return button.action
    return None


def modal_rect() -> sdl2.SDL_Rect:
    width = 760
    height = 440
    x = (current_width() - width) // 2
    y = (current_height() - height) // 2
    return sdl2.SDL_Rect(x, y, width, height)


def modal_button_layout(
    modal: ValidationModal,
) -> list[tuple[sdl2.SDL_Rect, ModalButton]]:
    rect = modal_rect()
    spacing = 14
    button_height = 46
    button_width = 180
    total_width = (
        len(modal.buttons) * button_width + max(0, len(modal.buttons) - 1) * spacing
    )
    start_x = rect.x + (rect.w - total_width) // 2
    y = rect.y + rect.h - 74

    layout: list[tuple[sdl2.SDL_Rect, ModalButton]] = []
    for idx, button in enumerate(modal.buttons):
        x = start_x + idx * (button_width + spacing)
        button_rect = sdl2.SDL_Rect(x, y, button_width, button_height)
        layout.append((button_rect, button))
    return layout


def draw_validation_modal(
    renderer: ctypes.c_void_p,
    text: TextRenderer,
    modal: ValidationModal,
) -> None:
    set_color(renderer, (0, 0, 0, 170))
    screen_rect = sdl2.SDL_Rect(0, 0, current_width(), current_height())
    sdl2.SDL_RenderFillRect(renderer, screen_rect)

    rect = modal_rect()
    set_color(renderer, (13, 16, 22, 245))
    sdl2.SDL_RenderFillRect(renderer, rect)
    set_color(renderer, modal.color)
    draw_rounded_rect_outline(renderer=renderer, rect=rect, radius=12)

    text.draw(modal.title, rect.x + 24, rect.y + 20, color=modal.color, size=28)
    y = rect.y + 66
    for line in modal.lines:
        y = text.wrap_draw(
            text=line,
            x=rect.x + 24,
            y=y,
            width=rect.w - 48,
            color=TEXT_COLOR,
            size=18,
            line_gap=2,
        ) + 4

    for button_rect, button in modal_button_layout(modal):
        set_color(renderer, (28, 35, 47, 255))
        draw_rounded_rect_filled(renderer=renderer, rect=button_rect, radius=8)
        set_color(renderer, modal.color)
        draw_rounded_rect_outline(renderer=renderer, rect=button_rect, radius=8)
        label_x = button_rect.x + 18
        label_y = button_rect.y + 14
        text.draw(button.label, label_x, label_y, color=TEXT_COLOR, size=16)


def draw_grid(renderer: ctypes.c_void_p) -> None:
    rect = canvas_rect()

    minor_step = GRID_SIZE
    major_step = GRID_SIZE * 5

    for x in range(rect.x, rect.x + rect.w + 1, minor_step):
        set_color(renderer, GRID_MINOR)
        sdl2.SDL_RenderDrawLine(renderer, x, rect.y, x, rect.y + rect.h)
    for y in range(rect.y, rect.y + rect.h + 1, minor_step):
        set_color(renderer, GRID_MINOR)
        sdl2.SDL_RenderDrawLine(renderer, rect.x, y, rect.x + rect.w, y)

    for x in range(rect.x, rect.x + rect.w + 1, major_step):
        set_color(renderer, GRID_MAJOR)
        sdl2.SDL_RenderDrawLine(renderer, x, rect.y, x, rect.y + rect.h)
    for y in range(rect.y, rect.y + rect.h + 1, major_step):
        set_color(renderer, GRID_MAJOR)
        sdl2.SDL_RenderDrawLine(renderer, rect.x, y, rect.x + rect.w, y)


def draw_sidebar(renderer: ctypes.c_void_p) -> None:
    sidebar = sdl2.SDL_Rect(0, 0, SIDEBAR_WIDTH, current_height())
    set_color(renderer, PANEL_COLOR)
    sdl2.SDL_RenderFillRect(renderer, sidebar)
    set_color(renderer, PANEL_BORDER)
    sdl2.SDL_RenderDrawRect(renderer, sidebar)


def draw_header(renderer: ctypes.c_void_p) -> None:
    header = sdl2.SDL_Rect(
        SIDEBAR_WIDTH,
        0,
        current_width() - SIDEBAR_WIDTH,
        HEADER_HEIGHT,
    )
    set_color(renderer, PANEL_COLOR)
    sdl2.SDL_RenderFillRect(renderer, header)
    set_color(renderer, PANEL_BORDER)
    sdl2.SDL_RenderDrawRect(renderer, header)


def draw_stage_text(text: TextRenderer, stage: Stage) -> None:
    left = SIDEBAR_WIDTH + 28
    top = 20

    text.draw("Flow Diagram Trainer", left, top, color=ACCENT, size=26)
    text.draw(stage.title, left, top + 34, color=TEXT_COLOR, size=22)

    task_x = left + 10
    task_y = top + 72
    task_width = max(240, current_width() - SIDEBAR_WIDTH - 110)
    task_text = f"Task: {stage.description}"
    line_gap = 4
    task_size = 16
    max_chars = max(20, task_width // max(7, task_size // 2 + 2))
    lines = wrap_text(text=task_text, max_chars=max_chars)
    task_end_y = task_y + len(lines) * (task_size + line_gap)
    task_box = sdl2.SDL_Rect(
        left,
        top + 66,
        task_width + 20,
        max(34, task_end_y - (top + 66) + 6),
    )
    set_color(text.renderer, (12, 14, 20, 220))
    draw_rounded_rect_filled(renderer=text.renderer, rect=task_box, radius=8)
    set_color(text.renderer, PANEL_BORDER)
    draw_rounded_rect_outline(renderer=text.renderer, rect=task_box, radius=8)
    cursor_y = task_y
    for line in lines:
        text.draw(line, task_x, cursor_y, color=SUBTEXT_COLOR, size=task_size)
        cursor_y += task_size + line_gap


def draw_controls(text: TextRenderer, builder: BuilderState) -> None:
    x = 20
    y = 16
    box = sdl2.SDL_Rect(16, 12, SIDEBAR_WIDTH - 32, 184)
    set_color(text.renderer, (12, 14, 20, 220))
    draw_rounded_rect_filled(renderer=text.renderer, rect=box, radius=8)
    set_color(text.renderer, PANEL_BORDER)
    draw_rounded_rect_outline(renderer=text.renderer, rect=box, radius=8)

    text.draw("Controls", x, y, color=ACCENT, size=22)
    text.draw("Left click block: select/move", x, y + 34, color=SUBTEXT_COLOR, size=15)
    text.draw(
        "Left click handle: start connector drag",
        x,
        y + 54,
        color=SUBTEXT_COLOR,
        size=15,
    )
    text.draw(
        "Click near target handle: connect",
        x,
        y + 74,
        color=SUBTEXT_COLOR,
        size=15,
    )
    text.draw("Right click node: remove", x, y + 94, color=SUBTEXT_COLOR, size=15)
    text.draw(
        "Enter: validate   X: undo edge   R: clear",
        x,
        y + 114,
        color=SUBTEXT_COLOR,
        size=15,
    )
    text.draw("Grid snap + 90° auto-routing", x, y + 134, color=SUBTEXT_COLOR, size=15)

    mode_text = (
        "Mode: CONNECT"
        if builder.drag_connector_source is not None
        else "Mode: EDIT"
    )
    mode_color = (
        HANDLE_ACTIVE
        if builder.drag_connector_source is not None
        else SUBTEXT_COLOR
    )
    text.draw(mode_text, x, y + 156, color=mode_color, size=16)


def draw_template_list(text: TextRenderer, stage: Stage, builder: BuilderState) -> None:
    left = 24
    top = HEADER_HEIGHT + 90

    text.draw("Select Block", left, top - 34, color=ACCENT, size=20)

    for index, node in enumerate(stage.expected_nodes):
        box = template_item_rect(index)
        item_top = box.y + 4
        is_placed = node.node_id in builder.placed_nodes
        is_selected = builder.selected_template == node.node_id

        color = (26, 30, 40, 255)
        if is_selected:
            color = (45, 62, 88, 255)
        elif is_placed:
            color = (35, 58, 50, 255)

        set_color(text.renderer, color)
        draw_rounded_rect_filled(renderer=text.renderer, rect=box, radius=8)
        set_color(text.renderer, PANEL_BORDER)
        draw_rounded_rect_outline(renderer=text.renderer, rect=box, radius=8)

        preview_rect = sdl2.SDL_Rect(left + 8, item_top + 8, 96, 56)
        draw_template_preview(renderer=text.renderer, node=node, rect=preview_rect)

        text.draw(node.node_id, left + 116, item_top + 8, color=TEXT_COLOR, size=15)
        text.draw(
            node.label,
            left + 116,
            item_top + 30,
            color=SUBTEXT_COLOR,
            size=14,
        )
        text.draw(
            node.block_type.value,
            left + 116,
            item_top + 50,
            color=SUBTEXT_COLOR,
            size=13,
        )


def template_item_rect(index: int) -> sdl2.SDL_Rect:
    left = 24
    top = HEADER_HEIGHT + 90
    item_height = 86
    item_top = top + index * item_height
    return sdl2.SDL_Rect(left - 4, item_top - 4, SIDEBAR_WIDTH - 36, item_height - 8)


def draw_swimlanes(renderer: ctypes.c_void_p, text: TextRenderer, stage: Stage) -> None:
    rect = canvas_rect()
    lane_height = rect.h // len(stage.lanes)

    for index, lane in enumerate(stage.lanes):
        lane_rect = sdl2.SDL_Rect(
            rect.x,
            rect.y + index * lane_height,
            rect.w,
            lane_height,
        )
        tint = (20, 25, 34, 255) if index % 2 == 0 else (16, 21, 30, 255)
        set_color(renderer, tint)
        sdl2.SDL_RenderFillRect(renderer, lane_rect)

        set_color(renderer, PANEL_BORDER)
        sdl2.SDL_RenderDrawRect(renderer, lane_rect)
        text.draw(lane, lane_rect.x + 10, lane_rect.y + 8, color=SUBTEXT_COLOR, size=14)


def draw_nodes(
    renderer: ctypes.c_void_p,
    text: TextRenderer,
    builder: BuilderState,
) -> None:
    for placed in builder.placed_nodes.values():
        rect = placed.rect

        fill_color = NODE_FILL
        border_color = NODE_BORDER
        if (
            builder.drag_node == placed.template.node_id
            and builder.drag_position_invalid
        ):
            fill_color = (45, 10, 10, 255)
            border_color = ERROR_COLOR

        set_color(renderer, fill_color)
        if placed.template.block_type.value == "decision":
            draw_diamond_filled(renderer=renderer, rect=rect)
            set_color(renderer, border_color)
            draw_diamond_outline(renderer=renderer, rect=rect)
        else:
            draw_rounded_rect_filled(renderer=renderer, rect=rect, radius=10)
            set_color(renderer, border_color)
            draw_rounded_rect_outline(renderer=renderer, rect=rect, radius=10)

        if builder.selected_node == placed.template.node_id:
            focus_rect = sdl2.SDL_Rect(rect.x - 2, rect.y - 2, rect.w + 4, rect.h + 4)
            set_color(renderer, HANDLE_COLOR)
            if placed.template.block_type.value == "decision":
                draw_diamond_outline(renderer=renderer, rect=focus_rect)
            else:
                draw_rounded_rect_outline(renderer=renderer, rect=focus_rect, radius=10)

        draw_centered_label_in_rect(
            text_renderer=text,
            label=placed.template.label,
            rect=rect,
            color=TEXT_COLOR,
        )


def draw_centered_label_in_rect(
    text_renderer: TextRenderer,
    label: str,
    rect: sdl2.SDL_Rect,
    color: tuple[int, int, int, int],
) -> None:
    padding_x = 10
    padding_y = 8
    available_w = max(8, rect.w - (2 * padding_x))
    available_h = max(8, rect.h - (2 * padding_y))

    best_size = MIN_BLOCK_LABEL_SIZE
    for size in range(MAX_BLOCK_LABEL_SIZE, MIN_BLOCK_LABEL_SIZE - 1, -1):
        width, height = text_renderer.text_size(label, size=size, color=color)
        if width <= available_w and height <= available_h:
            best_size = size
            break

    width, height = text_renderer.text_size(label, size=best_size, color=color)
    x = rect.x + (rect.w - width) // 2
    y = rect.y + (rect.h - height) // 2
    text_renderer.draw(label, x, y, color=color, size=best_size)


def draw_connector_handles(renderer: ctypes.c_void_p, builder: BuilderState) -> None:
    connected = connected_anchor_keys(builder)
    for node_id, placed in builder.placed_nodes.items():
        if node_id == builder.selected_node:
            continue
        points = connector_points(placed)
        connected_indexes = [
            idx for idx in range(len(points)) if (node_id, idx) in connected
        ]
        if not connected_indexes:
            continue
        draw_handles_for_node(
            renderer=renderer,
            builder=builder,
            node_id=node_id,
            points=points,
            visible_indexes=connected_indexes,
        )

    selected_node_id = builder.selected_node
    if selected_node_id is None:
        return

    selected_node = builder.placed_nodes.get(selected_node_id)
    if selected_node is None:
        return

    draw_handles_for_node(
        renderer=renderer,
        builder=builder,
        node_id=selected_node_id,
        points=connector_points(selected_node),
        connected=connected,
    )

    if builder.drag_target_connector is not None:
        target_node_id, _ = builder.drag_target_connector
        if target_node_id != selected_node_id:
            target_node = builder.placed_nodes.get(target_node_id)
            if target_node is not None:
                draw_handles_for_node(
                    renderer=renderer,
                    builder=builder,
                    node_id=target_node_id,
                    points=connector_points(target_node),
                    only_index=builder.drag_target_connector[1],
                    connected=connected,
                )


def draw_handles_for_node(
    renderer: ctypes.c_void_p,
    builder: BuilderState,
    node_id: str,
    points: list[tuple[int, int]],
    only_index: int | None = None,
    visible_indexes: list[int] | None = None,
    connected: set[tuple[str, int]] | None = None,
) -> None:
    if connected is None:
        connected = connected_anchor_keys(builder)

    for idx, (px, py) in enumerate(points):
        if only_index is not None and idx != only_index:
            continue
        if visible_indexes is not None and idx not in visible_indexes:
            continue
        key = (node_id, idx)
        is_connected = key in connected
        is_hovered = builder.hovered_connector == key
        is_source = builder.drag_connector_source == key
        is_target = builder.drag_target_connector == key
        color = (
            HANDLE_ACTIVE
            if (is_hovered or is_source or is_target)
            else HANDLE_COLOR
        )
        if is_connected and not (is_hovered or is_source or is_target):
            color = EDGE_COLOR
        radius = HANDLE_RADIUS + (2 if (is_hovered or is_source or is_target) else 0)
        if is_connected:
            radius += 1

        set_color(renderer, color)
        draw_circle_filled(renderer=renderer, cx=px, cy=py, radius=radius)
        set_color(renderer, NODE_BORDER)
        draw_circle_outline(renderer=renderer, cx=px, cy=py, radius=radius)


def connected_anchor_keys(builder: BuilderState) -> set[tuple[str, int]]:
    connected: set[tuple[str, int]] = set()
    for edge in builder.edges:
        connected.add((edge.source, edge.source_anchor))
        connected.add((edge.target, edge.target_anchor))
    return connected


def draw_edges(
    renderer: ctypes.c_void_p,
    text: TextRenderer,
    builder: BuilderState,
    stage: Stage,
) -> None:
    routed_edges = route_all_edge_paths(builder=builder, stage=stage)
    for edge, path in routed_edges:
        if len(path) < 2:
            continue
        edge_index = builder.edges.index(edge)
        is_selected = builder.selected_edge_index == edge_index

        edge_color = HANDLE_ACTIVE if is_selected else EDGE_COLOR
        set_color(renderer, edge_color)
        for idx in range(len(path) - 1):
            sx, sy = path[idx]
            tx, ty = path[idx + 1]
            if is_selected:
                if sx == tx:
                    sdl2.SDL_RenderDrawLine(renderer, sx + 1, sy, tx + 1, ty)
                elif sy == ty:
                    sdl2.SDL_RenderDrawLine(renderer, sx, sy + 1, tx, ty + 1)
            sdl2.SDL_RenderDrawLine(renderer, sx, sy, tx, ty)

        sx, sy = path[-2]
        tx, ty = path[-1]
        draw_arrow_head(renderer=renderer, sx=sx, sy=sy, tx=tx, ty=ty)

        if edge.label:
            mid_idx = len(path) // 2
            mx, my = path[mid_idx]
            mx += 8
            my -= 10
            label_color = HANDLE_ACTIVE if is_selected else EDGE_COLOR
            text.draw(edge.label, mx, my, color=label_color, size=15)


def draw_drag_connector_preview(
    renderer: ctypes.c_void_p,
    builder: BuilderState,
    stage: Stage,
) -> None:
    source_ref = builder.drag_connector_source
    mouse_pos = builder.drag_mouse_pos
    if source_ref is None or mouse_pos is None:
        return

    source_node_id, source_anchor = source_ref
    source_node = builder.placed_nodes.get(source_node_id)
    if source_node is None:
        return
    source_points = connector_points(source_node)
    if source_anchor >= len(source_points):
        return

    start = source_points[source_anchor]
    start_outside = anchor_outside_point(start, source_anchor)
    source_dir = anchor_direction(source_anchor)
    raw_stem = projected_distance(
        origin=start_outside,
        direction=source_dir,
        target=mouse_pos,
    )
    dynamic_stem = max(0, min(MIN_START_STEM, raw_stem))

    if builder.drag_target_connector is None and dynamic_stem < MIN_START_STEM:
        end_preview = (
            start_outside[0] + source_dir[0] * dynamic_stem,
            start_outside[1] + source_dir[1] * dynamic_stem,
        )
        set_color(renderer, HANDLE_COLOR)
        sdl2.SDL_RenderDrawLine(
            renderer,
            start_outside[0],
            start_outside[1],
            end_preview[0],
            end_preview[1],
        )
        draw_arrow_head(
            renderer=renderer,
            sx=start_outside[0],
            sy=start_outside[1],
            tx=end_preview[0],
            ty=end_preview[1],
        )
        return

    if builder.drag_target_connector is not None:
        target_node_id, target_anchor = builder.drag_target_connector
        target_node = builder.placed_nodes.get(target_node_id)
        if target_node is None:
            return
        target_points = connector_points(target_node)
        if target_anchor >= len(target_points):
            return
        end = target_points[target_anchor]
    else:
        end = snap_point_to_grid(mouse_pos[0], mouse_pos[1], rect=canvas_rect())
        target_anchor = source_anchor

    occupied_points, occupied_segments = collect_edge_occupancy(
        builder=builder,
        stage=stage,
    )
    path: list[tuple[int, int]] = []
    if builder.drag_target_connector is not None:
        path = route_path_between_points(
            builder=builder,
            stage=stage,
            start=start,
            end=end,
            ignore_nodes=set(),
            occupied_points=occupied_points,
            occupied_segments=occupied_segments,
            include_start_stem=True,
            stem_length=MIN_START_STEM,
            source_anchor=source_anchor,
            target_anchor=target_anchor,
            source_node_id=source_node_id,
            target_node_id=builder.drag_target_connector[0],
        )
    else:
        best_score: tuple[int, int, int] | None = None
        best_path: list[tuple[int, int]] = []
        best_anchor = target_anchor
        preview_anchors = preferred_preview_target_anchors(start=start, end=end)[:2]
        for preview_anchor in preview_anchors:
            candidate = route_path_between_points(
                builder=builder,
                stage=stage,
                start=start,
                end=end,
                ignore_nodes=set(),
                occupied_points=occupied_points,
                occupied_segments=occupied_segments,
                include_start_stem=True,
                stem_length=dynamic_stem,
                source_anchor=source_anchor,
                target_anchor=preview_anchor,
                source_node_id=source_node_id,
                preview_mode=True,
            )
            if not candidate:
                continue
            score = preview_path_score(candidate)
            if best_score is None or score < best_score:
                best_score = score
                best_path = candidate
                best_anchor = preview_anchor
        path = best_path
        target_anchor = best_anchor
    if len(path) < 2:
        return

    set_color(renderer, HANDLE_COLOR)
    for idx in range(len(path) - 1):
        sx, sy = path[idx]
        tx, ty = path[idx + 1]
        sdl2.SDL_RenderDrawLine(renderer, sx, sy, tx, ty)

    sx, sy = path[-2]
    tx, ty = path[-1]
    draw_arrow_head(renderer=renderer, sx=sx, sy=sy, tx=tx, ty=ty)


def draw_messages(text: TextRenderer, builder: BuilderState) -> None:
    left = SIDEBAR_WIDTH + 30
    bottom = current_height() - 18

    # Always place the latest message closest to the bottom edge.
    visible = builder.messages[-MAX_VISIBLE_MESSAGES:]
    box_height = MAX_VISIBLE_MESSAGES * 22 + 14
    box_top = bottom - box_height - 4
    box = sdl2.SDL_Rect(left - 10, box_top, current_width() - left - 24, box_height)
    set_color(text.renderer, (12, 14, 20, 220))
    sdl2.SDL_RenderFillRect(text.renderer, box)
    set_color(text.renderer, PANEL_BORDER)
    sdl2.SDL_RenderDrawRect(text.renderer, box)

    for index, (message, color) in enumerate(reversed(visible)):
        y = bottom - (index + 1) * 22
        text.draw(message, left, y, color=color, size=15)


def draw_template_preview(
    renderer: ctypes.c_void_p,
    node: DiagramNode,
    rect: sdl2.SDL_Rect,
) -> None:
    set_color(renderer, NODE_FILL)
    if node.block_type.value == "decision":
        inset = sdl2.SDL_Rect(rect.x + 8, rect.y + 2, rect.w - 16, rect.h - 4)
        draw_diamond_filled(renderer=renderer, rect=inset)
        set_color(renderer, NODE_BORDER)
        draw_diamond_outline(renderer=renderer, rect=inset)
    else:
        inset = sdl2.SDL_Rect(rect.x + 4, rect.y + 8, rect.w - 8, rect.h - 16)
        draw_rounded_rect_filled(renderer=renderer, rect=inset, radius=8)
        set_color(renderer, NODE_BORDER)
        draw_rounded_rect_outline(renderer=renderer, rect=inset, radius=8)


def draw_template_placement_preview(
    renderer: ctypes.c_void_p,
    builder: BuilderState,
    stage: Stage,
) -> None:
    template_id = builder.selected_template
    placement_pos = builder.placement_pos
    if template_id is None or placement_pos is None:
        return

    template = next(
        node for node in stage.expected_nodes if node.node_id == template_id
    )
    preview = PlacedNode(template=template, x=placement_pos[0], y=placement_pos[1])
    rect = preview.rect

    fill = (35, 42, 58, 255)
    border = HANDLE_COLOR
    if builder.placement_invalid:
        fill = (45, 10, 10, 255)
        border = ERROR_COLOR

    set_color(renderer, fill)
    if template.block_type.value == "decision":
        draw_diamond_filled(renderer=renderer, rect=rect)
        set_color(renderer, border)
        draw_diamond_outline(renderer=renderer, rect=rect)
    else:
        draw_rounded_rect_filled(renderer=renderer, rect=rect, radius=10)
        set_color(renderer, border)
        draw_rounded_rect_outline(renderer=renderer, rect=rect, radius=10)


def draw_complete_screen(
    renderer: ctypes.c_void_p,
    text: TextRenderer,
    game: FlowLearningGame,
) -> None:
    set_color(renderer, BG_COLOR)
    sdl2.SDL_RenderClear(renderer)

    width = current_width()
    height = current_height()
    text.draw(
        "All stages completed",
        max(40, width // 3),
        120,
        color=SUCCESS_COLOR,
        size=36,
    )
    text.draw("Badges earned", max(40, width // 3), 175, color=ACCENT, size=24)

    start_y = 220
    for index, badge in enumerate(sorted(game.badges)):
        text.draw(
            f"- {badge}",
            max(40, width // 3),
            start_y + index * 28,
            color=TEXT_COLOR,
            size=18,
        )

    text.draw(
        "Press R to restart or ESC to quit.",
        max(40, width // 3),
        max(40, height - 40),
        color=SUBTEXT_COLOR,
        size=18,
    )


def draw_arrow_head(
    renderer: ctypes.c_void_p,
    sx: int,
    sy: int,
    tx: int,
    ty: int,
) -> None:
    dx = tx - sx
    dy = ty - sy
    if dx == 0 and dy == 0:
        return

    head_length = ARROW_HEAD_LENGTH
    head_half_width = 4

    # Routed lines are orthogonal. Draw a filled triangular arrowhead that
    # points with the final segment direction.
    if abs(dx) >= abs(dy):
        direction = 1 if dx > 0 else -1
        for offset in range(head_length):
            span = int((offset / max(1, head_length - 1)) * head_half_width)
            x = tx - (direction * offset)
            sdl2.SDL_RenderDrawLine(renderer, x, ty - span, x, ty + span)
        return

    direction = 1 if dy > 0 else -1
    for offset in range(head_length):
        span = int((offset / max(1, head_length - 1)) * head_half_width)
        y = ty - (direction * offset)
        sdl2.SDL_RenderDrawLine(renderer, tx - span, y, tx + span, y)


def draw_diamond_outline(renderer: ctypes.c_void_p, rect: sdl2.SDL_Rect) -> None:
    cx = rect.x + rect.w // 2
    cy = rect.y + rect.h // 2
    top = (cx, rect.y)
    right = (rect.x + rect.w, cy)
    bottom = (cx, rect.y + rect.h)
    left = (rect.x, cy)

    sdl2.SDL_RenderDrawLine(renderer, top[0], top[1], right[0], right[1])
    sdl2.SDL_RenderDrawLine(renderer, right[0], right[1], bottom[0], bottom[1])
    sdl2.SDL_RenderDrawLine(renderer, bottom[0], bottom[1], left[0], left[1])
    sdl2.SDL_RenderDrawLine(renderer, left[0], left[1], top[0], top[1])


def draw_diamond_filled(renderer: ctypes.c_void_p, rect: sdl2.SDL_Rect) -> None:
    cx = rect.x + rect.w // 2
    cy = rect.y + rect.h // 2
    half_w = rect.w // 2
    half_h = rect.h // 2

    for y in range(-half_h, half_h + 1):
        ratio = 1.0 - abs(y) / max(1, half_h)
        span = int(half_w * ratio)
        sdl2.SDL_RenderDrawLine(renderer, cx - span, cy + y, cx + span, cy + y)


def draw_rounded_rect_filled(
    renderer: ctypes.c_void_p,
    rect: sdl2.SDL_Rect,
    radius: int,
) -> None:
    radius = max(1, min(radius, rect.w // 2, rect.h // 2))
    center = sdl2.SDL_Rect(rect.x + radius, rect.y, rect.w - (2 * radius), rect.h)
    sdl2.SDL_RenderFillRect(renderer, center)

    for dy in range(radius):
        span = int((radius * radius - (radius - dy) * (radius - dy)) ** 0.5)
        left = rect.x + radius - span
        right = rect.x + rect.w - radius + span
        y_top = rect.y + dy
        y_bottom = rect.y + rect.h - 1 - dy
        sdl2.SDL_RenderDrawLine(renderer, left, y_top, right, y_top)
        sdl2.SDL_RenderDrawLine(renderer, left, y_bottom, right, y_bottom)


def draw_rounded_rect_outline(
    renderer: ctypes.c_void_p,
    rect: sdl2.SDL_Rect,
    radius: int,
) -> None:
    radius = max(1, min(radius, rect.w // 2, rect.h // 2))
    x1 = rect.x
    y1 = rect.y
    x2 = rect.x + rect.w - 1
    y2 = rect.y + rect.h - 1

    sdl2.SDL_RenderDrawLine(renderer, x1 + radius, y1, x2 - radius, y1)
    sdl2.SDL_RenderDrawLine(renderer, x1 + radius, y2, x2 - radius, y2)
    sdl2.SDL_RenderDrawLine(renderer, x1, y1 + radius, x1, y2 - radius)
    sdl2.SDL_RenderDrawLine(renderer, x2, y1 + radius, x2, y2 - radius)

    for dy in range(radius + 1):
        dx = int((radius * radius - (radius - dy) * (radius - dy)) ** 0.5)
        lx = x1 + radius - dx
        rx = x2 - radius + dx
        ty = y1 + dy
        by = y2 - dy
        sdl2.SDL_RenderDrawPoint(renderer, lx, ty)
        sdl2.SDL_RenderDrawPoint(renderer, rx, ty)
        sdl2.SDL_RenderDrawPoint(renderer, lx, by)
        sdl2.SDL_RenderDrawPoint(renderer, rx, by)


def draw_circle_filled(
    renderer: ctypes.c_void_p,
    cx: int,
    cy: int,
    radius: int,
) -> None:
    for dy in range(-radius, radius + 1):
        span_sq = radius * radius - dy * dy
        if span_sq < 0:
            continue
        span = int(span_sq**0.5)
        sdl2.SDL_RenderDrawLine(renderer, cx - span, cy + dy, cx + span, cy + dy)


def draw_circle_outline(
    renderer: ctypes.c_void_p,
    cx: int,
    cy: int,
    radius: int,
) -> None:
    x = radius
    y = 0
    decision = 1 - x

    while y <= x:
        draw_circle_octants(renderer=renderer, cx=cx, cy=cy, x=x, y=y)
        y += 1
        if decision <= 0:
            decision += 2 * y + 1
        else:
            x -= 1
            decision += 2 * (y - x) + 1


def draw_circle_octants(
    renderer: ctypes.c_void_p,
    cx: int,
    cy: int,
    x: int,
    y: int,
) -> None:
    points = (
        (cx + x, cy + y),
        (cx + y, cy + x),
        (cx - y, cy + x),
        (cx - x, cy + y),
        (cx - x, cy - y),
        (cx - y, cy - x),
        (cx + y, cy - x),
        (cx + x, cy - y),
    )
    for px, py in points:
        sdl2.SDL_RenderDrawPoint(renderer, px, py)


def route_path_between_points(
    builder: BuilderState,
    stage: Stage,
    start: tuple[int, int],
    end: tuple[int, int],
    ignore_nodes: set[str],
    occupied_points: set[tuple[int, int]] | None = None,
    occupied_segments: set[tuple[tuple[int, int], tuple[int, int]]] | None = None,
    include_start_stem: bool = False,
    stem_length: int = MIN_START_STEM,
    source_anchor: int = 0,
    target_anchor: int = 0,
    source_node_id: str | None = None,
    target_node_id: str | None = None,
    preview_mode: bool = False,
) -> list[tuple[int, int]]:
    rect = canvas_rect()
    start_outer = anchor_outside_point(start, source_anchor)
    end_outer = anchor_outside_point(end, target_anchor)
    start_entry = start_outer
    if include_start_stem:
        start_entry = extend_point_by_anchor(
            point=start_outer,
            anchor_idx=source_anchor,
            distance=stem_length,
            rect=rect,
            snap=False,
        )
    start_grid = snap_point_to_grid(start_entry[0], start_entry[1], rect=rect)

    base_blocked = build_blocked_cells(
        builder=builder,
        stage=stage,
        ignore=ignore_nodes,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
    )
    # Allow route endpoints to escape/enter even when nearby blocked cells
    # touch these endpoint samples due to grid rounding.
    start_g = grid_from_pixel(start_grid[0], start_grid[1], rect)
    start_outer_g = grid_from_pixel(start_outer[0], start_outer[1], rect)
    start_entry_g = grid_from_pixel(start_entry[0], start_entry[1], rect)
    for endpoint_cell in (start_g, start_outer_g, start_entry_g):
        base_blocked.discard(endpoint_cell)
    sx, sy = anchor_direction(source_anchor)
    tx, ty = anchor_direction(target_anchor)
    start_escape = (start_g[0] + sx, start_g[1] + sy)
    if in_grid_bounds(start_escape[0], start_escape[1], rect):
        base_blocked.discard(start_escape)
    perp_dx, perp_dy = ty, -tx
    end_stub_candidates = [MIN_END_SEGMENT]
    if MIN_END_STUB_FALLBACK < MIN_END_SEGMENT:
        end_stub_candidates.append(MIN_END_STUB_FALLBACK)

    for end_stub in end_stub_candidates:
        end_entry = extend_point_by_anchor(
            point=end_outer,
            anchor_idx=target_anchor,
            distance=end_stub,
            rect=rect,
            snap=False,
        )
        end_grid = snap_point_to_grid(end_entry[0], end_entry[1], rect=rect)
        end_g = grid_from_pixel(end_grid[0], end_grid[1], rect)
        end_outer_g = grid_from_pixel(end_outer[0], end_outer[1], rect)
        end_entry_g = grid_from_pixel(end_entry[0], end_entry[1], rect)

        blocked = set(base_blocked)
        for endpoint_cell in (end_g, end_outer_g, end_entry_g):
            blocked.discard(endpoint_cell)
        end_escape = (end_g[0] + tx, end_g[1] + ty)
        if in_grid_bounds(end_escape[0], end_escape[1], rect):
            blocked.discard(end_escape)

        candidate_end_points = [
            end_g,
            (end_g[0] + perp_dx, end_g[1] + perp_dy),
            (end_g[0] - perp_dx, end_g[1] - perp_dy),
        ]
        end_candidates: list[tuple[tuple[int, int], set[tuple[int, int]]]] = []
        seen_end: set[tuple[int, int]] = set()
        for candidate_end in candidate_end_points:
            if candidate_end in seen_end:
                continue
            seen_end.add(candidate_end)
            if not in_grid_bounds(candidate_end[0], candidate_end[1], rect):
                continue
            primary_pre_end = (candidate_end[0] + tx, candidate_end[1] + ty)
            if not in_grid_bounds(primary_pre_end[0], primary_pre_end[1], rect):
                continue
            # Strict pass: require outward-side entry into the end cell.
            end_candidates.append((candidate_end, {primary_pre_end}))
            # Relaxed pass: also allow side entries if strict routing fails.
            relaxed_pre_end = {
                primary_pre_end,
                (candidate_end[0] + perp_dx, candidate_end[1] + perp_dy),
                (candidate_end[0] - perp_dx, candidate_end[1] - perp_dy),
            }
            relaxed_pre_end = {
                cell
                for cell in relaxed_pre_end
                if in_grid_bounds(cell[0], cell[1], rect)
            }
            if relaxed_pre_end != {primary_pre_end}:
                end_candidates.append((candidate_end, relaxed_pre_end))

        for candidate_end, allowed_pre_end in end_candidates:
            candidate_blocked = set(blocked)
            candidate_blocked.discard(candidate_end)
            for allowed_cell in allowed_pre_end:
                candidate_blocked.discard(allowed_cell)
            candidate_end_pixel = pixel_from_grid(
                candidate_end[0],
                candidate_end[1],
                rect,
            )
            candidate_path = find_orthogonal_path(
                start=start_grid,
                end=candidate_end_pixel,
                blocked=candidate_blocked,
                rect=rect,
                occupied_points=occupied_points or set(),
                occupied_segments=occupied_segments or set(),
                required_pre_end=allowed_pre_end,
                turn_penalties=(
                    PREVIEW_PATHFINDING_TURN_PENALTIES
                    if preview_mode
                    else PATHFINDING_TURN_PENALTIES
                ),
                max_expanded=(
                    PREVIEW_PATHFINDING_MAX_EXPANDED
                    if preview_mode
                    else PATHFINDING_MAX_EXPANDED
                ),
            )
            if not candidate_path:
                continue

            full_path: list[tuple[int, int]] = [start_outer]
            append_orthogonal_segment(full_path, start_entry)
            append_orthogonal_segment(full_path, start_grid)
            for point in candidate_path[1:]:
                append_orthogonal_segment(full_path, point)
            append_orthogonal_segment(full_path, end_entry)
            append_orthogonal_segment(full_path, end_outer)
            return compress_collinear(full_path)

    return []


def route_all_edge_paths(
    builder: BuilderState,
    stage: Stage,
    edges: list[BuiltEdge] | None = None,
) -> list[tuple[BuiltEdge, list[tuple[int, int]]]]:
    routed: list[tuple[BuiltEdge, list[tuple[int, int]]]] = []
    occupied_points: set[tuple[int, int]] = set()
    occupied_segments: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    edge_list = edges if edges is not None else builder.edges

    for edge in edge_list:
        source_node = builder.placed_nodes.get(edge.source)
        target_node = builder.placed_nodes.get(edge.target)
        if source_node is None or target_node is None:
            continue

        source_points = connector_points(source_node)
        target_points = connector_points(target_node)
        if (
            edge.source_anchor >= len(source_points)
            or edge.target_anchor >= len(target_points)
        ):
            continue

        path = route_path_between_points(
            builder=builder,
            stage=stage,
            start=source_points[edge.source_anchor],
            end=target_points[edge.target_anchor],
            ignore_nodes=set(),
            occupied_points=occupied_points,
            occupied_segments=occupied_segments,
            include_start_stem=True,
            source_anchor=edge.source_anchor,
            target_anchor=edge.target_anchor,
            source_node_id=edge.source,
            target_node_id=edge.target,
        )
        if len(path) < 2:
            routed.append((edge, []))
            continue
        mark_path_occupancy(
            path=path,
            occupied_points=occupied_points,
            occupied_segments=occupied_segments,
        )
        routed.append((edge, path))

    return routed


def collect_edge_occupancy(
    builder: BuilderState,
    stage: Stage,
) -> tuple[
    set[tuple[int, int]],
    set[tuple[tuple[int, int], tuple[int, int]]],
]:
    routed = route_all_edge_paths(builder=builder, stage=stage)
    occupied_points: set[tuple[int, int]] = set()
    occupied_segments: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for _, path in routed:
        mark_path_occupancy(
            path=path,
            occupied_points=occupied_points,
            occupied_segments=occupied_segments,
        )
    return occupied_points, occupied_segments


def can_route_all_edges(builder: BuilderState, stage: Stage) -> bool:
    if not builder.edges:
        return True
    routed = route_all_edge_paths(builder=builder, stage=stage)
    if len(routed) != len(builder.edges):
        return False
    return all(len(path) > 1 for _, path in routed)


def can_place_template_at(
    builder: BuilderState,
    template: DiagramNode,
    x: int,
    y: int,
) -> bool:
    if template.node_id in builder.placed_nodes:
        return False

    probe = PlacedNode(template=template, x=x, y=y)
    probe_rect = probe.rect
    for node in builder.placed_nodes.values():
        if not respects_block_clearance(probe_rect, node.rect):
            return False
    return True


def has_min_block_spacing(
    builder: BuilderState,
    moving_node_id: str,
) -> bool:
    moving = builder.placed_nodes.get(moving_node_id)
    if moving is None:
        return True

    moving_rect = moving.rect
    for node_id, node in builder.placed_nodes.items():
        if node_id == moving_node_id:
            continue
        if not respects_block_clearance(moving_rect, node.rect):
            return False
    return True


def respects_block_clearance(a: sdl2.SDL_Rect, b: sdl2.SDL_Rect) -> bool:
    gap_x = max(a.x - (b.x + b.w), b.x - (a.x + a.w), 0)
    gap_y = max(a.y - (b.y + b.h), b.y - (a.y + a.h), 0)

    if gap_x == 0 and gap_y == 0:
        return False

    # Diagonal neighbors get a smaller spacing requirement.
    if gap_x > 0 and gap_y > 0:
        return gap_x >= DIAGONAL_BLOCK_GAP and gap_y >= DIAGONAL_BLOCK_GAP

    if gap_x > 0:
        return gap_x >= MIN_BLOCK_GAP
    return gap_y >= MIN_BLOCK_GAP


def is_valid_drag_position(
    builder: BuilderState,
    stage: Stage,
    moving_node_id: str | None,
) -> bool:
    if moving_node_id is None:
        return True
    if not has_min_block_spacing(builder=builder, moving_node_id=moving_node_id):
        return False
    if not builder.edges:
        return True
    return can_route_all_edges(builder=builder, stage=stage)


def route_to_nearby_end_for_preview(
    builder: BuilderState,
    stage: Stage,
    start: tuple[int, int],
    desired_end: tuple[int, int],
    ignore_nodes: set[str],
    occupied_points: set[tuple[int, int]],
    occupied_segments: set[tuple[tuple[int, int], tuple[int, int]]],
    source_anchor: int,
    target_anchor: int,
    stem_length: int,
    source_node_id: str | None = None,
    target_node_id: str | None = None,
) -> list[tuple[int, int]]:
    rect = canvas_rect()
    end_grid = grid_from_pixel(desired_end[0], desired_end[1], rect)
    candidates: list[tuple[int, int]] = [end_grid]

    for ring in range(1, 6):
        for dx in range(-ring, ring + 1):
            dy = ring - abs(dx)
            for signed_dy in (dy, -dy):
                candidates.append((end_grid[0] + dx, end_grid[1] + signed_dy))

    seen: set[tuple[int, int]] = set()
    for gx, gy in candidates:
        if (gx, gy) in seen:
            continue
        seen.add((gx, gy))
        if not in_grid_bounds(gx, gy, rect):
            continue
        candidate_end = pixel_from_grid(gx, gy, rect)
        path = route_path_between_points(
            builder=builder,
            stage=stage,
            start=start,
            end=candidate_end,
            ignore_nodes=ignore_nodes,
            occupied_points=occupied_points,
            occupied_segments=occupied_segments,
            include_start_stem=True,
            stem_length=stem_length,
            source_anchor=source_anchor,
            target_anchor=target_anchor,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
        )
        if path:
            return path
    return []


def build_blocked_cells(
    builder: BuilderState,
    stage: Stage,
    ignore: set[str],
    source_node_id: str | None = None,
    target_node_id: str | None = None,
) -> set[tuple[int, int]]:
    del stage  # stage reserved for future lane-aware routing tweaks.
    del source_node_id, target_node_id
    rect = canvas_rect()
    blocked: set[tuple[int, int]] = set()

    for node_id, node in builder.placed_nodes.items():
        if node_id in ignore:
            continue
        node_rect = node.rect
        inflated_x = node_rect.x - CONNECTOR_OBJECT_CLEARANCE
        inflated_y = node_rect.y - CONNECTOR_OBJECT_CLEARANCE
        inflated_w = node_rect.w + (2 * CONNECTOR_OBJECT_CLEARANCE)
        inflated_h = node_rect.h + (2 * CONNECTOR_OBJECT_CLEARANCE)
        min_gx = (inflated_x - rect.x) // GRID_SIZE
        min_gy = (inflated_y - rect.y) // GRID_SIZE
        max_gx = (inflated_x + inflated_w - 1 - rect.x) // GRID_SIZE
        max_gy = (inflated_y + inflated_h - 1 - rect.y) // GRID_SIZE
        min_gx = max(0, min(min_gx, rect.w // GRID_SIZE))
        min_gy = max(0, min(min_gy, rect.h // GRID_SIZE))
        max_gx = max(0, min(max_gx, rect.w // GRID_SIZE))
        max_gy = max(0, min(max_gy, rect.h // GRID_SIZE))
        for gx in range(min_gx, max_gx + 1):
            for gy in range(min_gy, max_gy + 1):
                if in_grid_bounds(gx, gy, rect):
                    blocked.add((gx, gy))
    return blocked


def find_orthogonal_path(
    start: tuple[int, int],
    end: tuple[int, int],
    blocked: set[tuple[int, int]],
    rect: sdl2.SDL_Rect,
    occupied_points: set[tuple[int, int]],
    occupied_segments: set[tuple[tuple[int, int], tuple[int, int]]],
    required_pre_end: set[tuple[int, int]] | None = None,
    turn_penalties: tuple[int, ...] | None = None,
    max_expanded: int | None = None,
) -> list[tuple[int, int]]:
    best_path: list[tuple[int, int]] = []
    best_score: tuple[int, int] | None = None
    penalties = turn_penalties or PATHFINDING_TURN_PENALTIES
    budget = max_expanded or PATHFINDING_MAX_EXPANDED
    for turn_penalty in penalties:
        candidate = find_orthogonal_path_single_pass(
            start=start,
            end=end,
            blocked=blocked,
            rect=rect,
            occupied_points=occupied_points,
            occupied_segments=occupied_segments,
            required_pre_end=required_pre_end,
            turn_penalty=turn_penalty,
            max_expanded=budget,
        )
        if not candidate:
            continue
        candidate_score = path_efficiency_score(candidate)
        if best_score is None or candidate_score < best_score:
            best_score = candidate_score
            best_path = candidate
        if candidate_score[0] <= 1:
            break
    return best_path


def find_orthogonal_path_single_pass(
    start: tuple[int, int],
    end: tuple[int, int],
    blocked: set[tuple[int, int]],
    rect: sdl2.SDL_Rect,
    occupied_points: set[tuple[int, int]],
    occupied_segments: set[tuple[tuple[int, int], tuple[int, int]]],
    required_pre_end: set[tuple[int, int]] | None,
    turn_penalty: int,
    max_expanded: int,
) -> list[tuple[int, int]]:
    start_g = grid_from_pixel(start[0], start[1], rect)
    end_g = grid_from_pixel(end[0], end[1], rect)
    start_state = (start_g[0], start_g[1], -1)
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1))

    open_heap: list[tuple[int, int, tuple[int, int, int]]] = []
    heapq.heappush(open_heap, (0, 0, start_state))

    came_from: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    g_score: dict[tuple[int, int, int], int] = {start_state: 0}
    visited: set[tuple[int, int, int]] = set()
    path_points_occupancy: dict[tuple[int, int, int], set[tuple[int, int]]] = {
        start_state: {start_g}
    }
    expanded = 0

    while open_heap:
        _, cost, current_state = heapq.heappop(open_heap)
        if current_state in visited:
            continue
        visited.add(current_state)
        expanded += 1
        if expanded > max_expanded:
            break

        cx, cy, current_dir = current_state
        current = (cx, cy)
        if current == end_g:
            return reconstruct_path_with_direction(came_from, current_state, rect)

        for dir_idx, (dx, dy) in enumerate(directions):
            nx, ny = (cx + dx, cy + dy)
            neighbor = (nx, ny)
            if not in_grid_bounds(nx, ny, rect):
                continue
            if neighbor in blocked and neighbor != end_g:
                continue
            if neighbor in occupied_points and neighbor not in (start_g, end_g):
                continue
            if transition_key(current, neighbor) in occupied_segments:
                continue
            if (
                required_pre_end is not None
                and neighbor == end_g
                and current not in required_pre_end
            ):
                continue
            current_points = path_points_occupancy.get(current_state, {start_g})
            if neighbor in current_points and neighbor != end_g:
                continue

            turn_cost = (
                turn_penalty
                if current_dir != -1 and current_dir != dir_idx
                else 0
            )
            tentative_g = cost + 1 + turn_cost
            neighbor_state = (nx, ny, dir_idx)
            if tentative_g >= g_score.get(neighbor_state, 10**9):
                continue

            came_from[neighbor_state] = current_state
            g_score[neighbor_state] = tentative_g
            path_points_occupancy[neighbor_state] = {*current_points, neighbor}
            h = abs(end_g[0] - nx) + abs(end_g[1] - ny)
            heapq.heappush(
                open_heap,
                (tentative_g + h, tentative_g, neighbor_state),
            )

    return []


def reconstruct_path_with_direction(
    came_from: dict[tuple[int, int, int], tuple[int, int, int]],
    current: tuple[int, int, int],
    rect: sdl2.SDL_Rect,
) -> list[tuple[int, int]]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return [pixel_from_grid(gx, gy, rect) for gx, gy, _ in path]


def path_efficiency_score(path: list[tuple[int, int]]) -> tuple[int, int]:
    if len(path) < 2:
        return (10**9, 10**9)
    segments = len(path) - 1
    length = 0
    for idx in range(segments):
        sx, sy = path[idx]
        tx, ty = path[idx + 1]
        length += abs(tx - sx) + abs(ty - sy)
    return (segments, length)


def mark_path_occupancy(
    path: list[tuple[int, int]],
    occupied_points: set[tuple[int, int]],
    occupied_segments: set[tuple[tuple[int, int], tuple[int, int]]],
) -> None:
    rect = canvas_rect()
    for idx in range(len(path) - 1):
        start_g = grid_from_pixel(path[idx][0], path[idx][1], rect)
        end_g = grid_from_pixel(path[idx + 1][0], path[idx + 1][1], rect)
        gx, gy = start_g
        tx, ty = end_g
        step_x = 0 if gx == tx else (1 if tx > gx else -1)
        step_y = 0 if gy == ty else (1 if ty > gy else -1)

        occupied_points.add((gx, gy))
        while (gx, gy) != (tx, ty):
            next_g = (gx + step_x, gy + step_y)
            occupied_segments.add(transition_key((gx, gy), next_g))
            occupied_points.add(next_g)
            gx, gy = next_g


def transition_key(
    first: tuple[int, int],
    second: tuple[int, int],
) -> tuple[tuple[int, int], tuple[int, int]]:
    return (first, second) if first <= second else (second, first)


def anchor_outside_point(point: tuple[int, int], anchor_idx: int) -> tuple[int, int]:
    dx, dy = anchor_direction(anchor_idx)
    return (
        point[0] + dx * (HANDLE_RADIUS + 1),
        point[1] + dy * (HANDLE_RADIUS + 1),
    )


def extend_point_by_anchor(
    point: tuple[int, int],
    anchor_idx: int,
    distance: int,
    rect: sdl2.SDL_Rect,
    snap: bool = True,
) -> tuple[int, int]:
    dx, dy = anchor_direction(anchor_idx)
    extended = (
        point[0] + dx * distance,
        point[1] + dy * distance,
    )
    if snap:
        return snap_point_to_grid(extended[0], extended[1], rect)
    return (
        max(rect.x, min(extended[0], rect.x + rect.w)),
        max(rect.y, min(extended[1], rect.y + rect.h)),
    )


def anchor_direction(anchor_idx: int) -> tuple[int, int]:
    if anchor_idx == 0:
        return (0, -1)
    if anchor_idx == 1:
        return (1, 0)
    if anchor_idx == 2:
        return (0, 1)
    return (-1, 0)


def target_anchor_from_point(placed: PlacedNode, point: tuple[int, int]) -> int:
    pts = connector_points(placed)
    best_idx = 0
    best_dist = 10**9
    for idx, (px, py) in enumerate(pts):
        dx = point[0] - px
        dy = point[1] - py
        dist = dx * dx + dy * dy
        if dist < best_dist:
            best_dist = dist
            best_idx = idx
    return best_idx


def append_orthogonal_segment(
    points: list[tuple[int, int]],
    target: tuple[int, int],
) -> None:
    if not points:
        points.append(target)
        return

    current = points[-1]
    if current == target:
        return

    if current[0] == target[0] or current[1] == target[1]:
        points.append(target)
        return

    elbow = (target[0], current[1])
    if elbow != current:
        points.append(elbow)
    if target != points[-1]:
        points.append(target)


def projected_distance(
    origin: tuple[int, int],
    direction: tuple[int, int],
    target: tuple[int, int],
) -> int:
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    return max(0, dx * direction[0] + dy * direction[1])


def preferred_preview_target_anchors(
    start: tuple[int, int],
    end: tuple[int, int],
) -> list[int]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    if abs(dx) >= abs(dy):
        primary = 1 if dx >= 0 else 3
        secondary = 2 if dy >= 0 else 0
    else:
        primary = 2 if dy >= 0 else 0
        secondary = 1 if dx >= 0 else 3

    opposite = (primary + 2) % 4
    ordered = [primary, secondary, opposite, (secondary + 2) % 4]
    unique: list[int] = []
    for anchor in ordered:
        if anchor not in unique:
            unique.append(anchor)
    return unique


def preview_path_score(path: list[tuple[int, int]]) -> tuple[int, int, int]:
    if len(path) < 2:
        return (10**9, 10**9, 10**9)
    segments = len(path) - 1
    bends = max(0, segments - 1)
    length = 0
    for idx in range(segments):
        sx, sy = path[idx]
        tx, ty = path[idx + 1]
        length += abs(tx - sx) + abs(ty - sy)
    return (segments, bends, length)


def compress_collinear(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(points) <= 2:
        return points

    reduced = [points[0]]
    for idx in range(1, len(points) - 1):
        ax, ay = reduced[-1]
        bx, by = points[idx]
        cx, cy = points[idx + 1]
        if (ax == bx == cx) or (ay == by == cy):
            continue
        reduced.append((bx, by))
    reduced.append(points[-1])
    return reduced


def clamp_node_position(
    stage: Stage,
    node: PlacedNode,
    x: int,
    y: int,
    width: int,
    height: int,
) -> tuple[int, int]:
    rect = canvas_rect()
    half_w = width // 2
    half_h = height // 2

    border_padding = GRID_SIZE
    min_center_x = rect.x + border_padding + half_w
    max_center_x = rect.x + rect.w - border_padding - half_w
    min_center_y = rect.y + border_padding + half_h
    max_center_y = rect.y + rect.h - border_padding - half_h

    center_x = x + half_w
    center_y = y + half_h

    center_x = max(min_center_x, min(center_x, max_center_x))
    center_y = max(min_center_y, min(center_y, max_center_y))
    center_x, center_y = snap_point_to_grid(center_x, center_y, rect=rect)
    center_x = max(min_center_x, min(center_x, max_center_x))
    center_y = max(min_center_y, min(center_y, max_center_y))

    if not stage.lanes:
        return (center_x - half_w, center_y - half_h)

    target_lane = node.template.lane
    lane_height = rect.h // len(stage.lanes)
    lane_index = stage.lanes.index(target_lane)

    lane_min_center_y = rect.y + lane_index * lane_height + 6 + half_h
    lane_max_center_y = rect.y + (lane_index + 1) * lane_height - 6 - half_h
    lane_min_center_y = max(lane_min_center_y, min_center_y)
    lane_max_center_y = min(lane_max_center_y, max_center_y)
    center_y = max(lane_min_center_y, min(center_y, lane_max_center_y))
    center_x, center_y = snap_point_to_grid(center_x, center_y, rect=rect)
    center_x = max(min_center_x, min(center_x, max_center_x))
    center_y = max(lane_min_center_y, min(center_y, lane_max_center_y))
    return (center_x - half_w, center_y - half_h)


def lane_from_position(stage: Stage, y: int, rect: sdl2.SDL_Rect) -> str:
    lane_height = rect.h / len(stage.lanes)
    index = int((y - rect.y) / lane_height)
    index = max(0, min(index, len(stage.lanes) - 1))
    return stage.lanes[index]


def canvas_rect() -> sdl2.SDL_Rect:
    return sdl2.SDL_Rect(
        SIDEBAR_WIDTH + CANVAS_MARGIN,
        HEADER_HEIGHT + CANVAS_MARGIN,
        current_width() - SIDEBAR_WIDTH - (2 * CANVAS_MARGIN),
        current_height() - HEADER_HEIGHT - (2 * CANVAS_MARGIN),
    )


def snap_point_to_grid(x: int, y: int, rect: sdl2.SDL_Rect) -> tuple[int, int]:
    gx, gy = grid_from_pixel(x, y, rect)
    return pixel_from_grid(gx, gy, rect)


def grid_from_pixel(x: int, y: int, rect: sdl2.SDL_Rect) -> tuple[int, int]:
    gx = round((x - rect.x) / GRID_SIZE)
    gy = round((y - rect.y) / GRID_SIZE)
    max_gx = rect.w // GRID_SIZE
    max_gy = rect.h // GRID_SIZE
    return (
        max(0, min(gx, max_gx)),
        max(0, min(gy, max_gy)),
    )


def pixel_from_grid(gx: int, gy: int, rect: sdl2.SDL_Rect) -> tuple[int, int]:
    return (rect.x + gx * GRID_SIZE, rect.y + gy * GRID_SIZE)


def in_grid_bounds(gx: int, gy: int, rect: "sdl2.SDL_Rect") -> bool:
    return 0 <= gx <= rect.w // GRID_SIZE and 0 <= gy <= rect.h // GRID_SIZE


def point_in_rect(x: int, y: int, rect: sdl2.SDL_Rect) -> bool:
    return rect.x <= x <= rect.x + rect.w and rect.y <= y <= rect.y + rect.h


def point_in_diamond(x: int, y: int, rect: sdl2.SDL_Rect) -> bool:
    cx = rect.x + rect.w / 2
    cy = rect.y + rect.h / 2
    dx = abs(x - cx)
    dy = abs(y - cy)
    if rect.w == 0 or rect.h == 0:
        return False
    return (dx / (rect.w / 2)) + (dy / (rect.h / 2)) <= 1


def set_color(renderer: ctypes.c_void_p, color: tuple[int, int, int, int]) -> None:
    sdl2.SDL_SetRenderDrawColor(renderer, color[0], color[1], color[2], color[3])


def find_font_path() -> str | None:
    candidates = (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    )

    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]

    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        lines.append(current)
        current = word

    lines.append(current)
    return lines
