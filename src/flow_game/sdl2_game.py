from __future__ import annotations

import ctypes
import heapq
import os
from dataclasses import dataclass, field

try:
    import sdl2
    from sdl2 import sdlttf
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    sdl2 = None  # type: ignore[assignment]
    sdlttf = None  # type: ignore[assignment]
    SDL_IMPORT_ERROR: ModuleNotFoundError | None = exc
else:
    SDL_IMPORT_ERROR = None

from .game import DiagramEdge, DiagramNode, FlowLearningGame, Stage

WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
SIDEBAR_WIDTH = 390
HEADER_HEIGHT = 170
CANVAS_MARGIN = 20
GRID_SIZE = 24

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


@dataclass
class PlacedNode:
    template: DiagramNode
    x: int
    y: int

    @property
    def size(self) -> tuple[int, int]:
        if self.template.block_type.value == "decision":
            return (144, 104)
        return (176, 72)

    @property
    def rect(self) -> sdl2.SDL_Rect:
        width, height = self.size
        return sdl2.SDL_Rect(self.x, self.y, width, height)

    @property
    def center(self) -> tuple[int, int]:
        width, height = self.size
        return (self.x + width // 2, self.y + height // 2)


@dataclass
class BuilderState:
    placed_nodes: dict[str, PlacedNode] = field(default_factory=dict)
    edges: list[DiagramEdge] = field(default_factory=list)
    selected_template: str | None = None
    edge_mode: bool = False
    edge_source: str | None = None
    drag_node: str | None = None
    drag_offset: tuple[int, int] = (0, 0)
    messages: list[tuple[str, tuple[int, int, int, int]]] = field(default_factory=list)

    def reset_for_stage(self) -> None:
        self.placed_nodes.clear()
        self.edges.clear()
        self.selected_template = None
        self.edge_mode = False
        self.edge_source = None
        self.drag_node = None
        self.drag_offset = (0, 0)
        self.messages.clear()

    def push_message(self, text: str, color: tuple[int, int, int, int]) -> None:
        self.messages.append((text, color))
        self.messages = self.messages[-6:]


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
        sdl2.SDL_WINDOW_SHOWN,
    )
    if not window:
        sdlttf.TTF_Quit()
        sdl2.SDL_Quit()
        raise RuntimeError("Could not create SDL2 window.")

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

    running = True
    event = sdl2.SDL_Event()

    while running:
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

        draw_frame(renderer=renderer, text=text, game=game, builder=builder)


def handle_keydown(game: FlowLearningGame, builder: BuilderState, key: int) -> bool:
    if key == sdl2.SDLK_ESCAPE:
        return False

    if game.is_completed():
        if key == sdl2.SDLK_r:
            game.current_stage_index = 0
            game.badges.clear()
            game.attempts_by_stage.clear()
            builder.reset_for_stage()
            builder.push_message("Game reset.", SUBTEXT_COLOR)
        return True

    if key == sdl2.SDLK_TAB:
        builder.edge_mode = not builder.edge_mode
        builder.edge_source = None
        mode = "Edge mode" if builder.edge_mode else "Move mode"
        builder.push_message(f"{mode} enabled.", SUBTEXT_COLOR)
        return True

    if key == sdl2.SDLK_RETURN:
        submit_stage(game=game, builder=builder)
        return True

    if key == sdl2.SDLK_x:
        if builder.edges:
            builder.edges.pop()
            builder.push_message("Last edge removed.", SUBTEXT_COLOR)
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
    if game.is_completed():
        return

    mouse_x = int(event.x)
    mouse_y = int(event.y)
    stage = game.current_stage()

    if event.button == sdl2.SDL_BUTTON_LEFT:
        template_id = find_template_click(stage=stage, x=mouse_x, y=mouse_y)
        if template_id is not None:
            builder.selected_template = template_id
            builder.push_message(
                f"Selected {template_id}. Click canvas to place.",
                SUBTEXT_COLOR,
            )
            return

        hit_node = find_node_hit(builder=builder, x=mouse_x, y=mouse_y)
        if hit_node is not None:
            if builder.edge_mode:
                handle_edge_selection(stage=stage, builder=builder, node_id=hit_node)
                return

            placed = builder.placed_nodes[hit_node]
            builder.drag_node = hit_node
            builder.drag_offset = (mouse_x - placed.x, mouse_y - placed.y)
            return

        if builder.selected_template is not None:
            if point_in_rect(mouse_x, mouse_y, canvas_rect()):
                place_selected_node(
                    game=game,
                    builder=builder,
                    x=mouse_x,
                    y=mouse_y,
                )
                return

    if event.button == sdl2.SDL_BUTTON_RIGHT:
        hit_node = find_node_hit(builder=builder, x=mouse_x, y=mouse_y)
        if hit_node is not None:
            remove_node(builder=builder, node_id=hit_node)


def handle_mouse_up(builder: BuilderState, event: sdl2.SDL_MouseButtonEvent) -> None:
    if event.button == sdl2.SDL_BUTTON_LEFT:
        builder.drag_node = None


def handle_mouse_motion(
    game: FlowLearningGame,
    builder: BuilderState,
    event: sdl2.SDL_MouseMotionEvent,
) -> None:
    if game.is_completed():
        return

    if builder.drag_node is None:
        return

    stage = game.current_stage()
    node = builder.placed_nodes[builder.drag_node]
    offset_x, offset_y = builder.drag_offset

    width, height = node.size
    target_x = int(event.x) - offset_x
    target_y = int(event.y) - offset_y
    node.x, node.y = clamp_node_position(
        stage=stage,
        node=node,
        x=target_x,
        y=target_y,
        width=width,
        height=height,
    )


def handle_edge_selection(stage: Stage, builder: BuilderState, node_id: str) -> None:
    if builder.edge_source is None:
        builder.edge_source = node_id
        builder.push_message(f"Edge source: {node_id}. Select target.", SUBTEXT_COLOR)
        return

    if builder.edge_source == node_id:
        builder.edge_source = None
        builder.push_message("Edge source cleared.", SUBTEXT_COLOR)
        return

    source = builder.edge_source
    target = node_id
    builder.edge_source = None

    if any(edge.source == source and edge.target == target for edge in builder.edges):
        builder.push_message("Edge already exists.", ERROR_COLOR)
        return

    expected_label = ""
    for edge in stage.expected_edges:
        if edge.source == source and edge.target == target:
            expected_label = edge.label
            break

    builder.edges.append(
        DiagramEdge(source=source, target=target, label=expected_label)
    )
    builder.push_message(f"Edge added: {source} -> {target}", SUBTEXT_COLOR)


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
    builder.selected_template = None
    builder.push_message(f"Placed {template_id}.", SUBTEXT_COLOR)


def remove_node(builder: BuilderState, node_id: str) -> None:
    if node_id not in builder.placed_nodes:
        return

    del builder.placed_nodes[node_id]
    builder.edges = [
        edge
        for edge in builder.edges
        if edge.source != node_id and edge.target != node_id
    ]
    builder.push_message(f"Removed {node_id} and connected edges.", SUBTEXT_COLOR)


def submit_stage(game: FlowLearningGame, builder: BuilderState) -> None:
    if game.is_completed():
        return

    stage = game.current_stage()
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
        edges=tuple(builder.edges),
    )

    if result.passed:
        builder.push_message("Stage complete.", SUCCESS_COLOR)
        for badge in result.earned_badges:
            builder.push_message(f"Badge earned: {badge}", SUCCESS_COLOR)
        builder.reset_for_stage()
    else:
        builder.push_message(
            "Diagram not correct. Press R to retry quickly.",
            ERROR_COLOR,
        )
        for error in result.errors[:3]:
            builder.push_message(error, ERROR_COLOR)


def find_template_click(stage: Stage, x: int, y: int) -> str | None:
    panel_left = 20
    panel_top = HEADER_HEIGHT + 30
    item_height = 68

    for index, node in enumerate(stage.expected_nodes):
        item_rect = sdl2.SDL_Rect(
            panel_left,
            panel_top + index * item_height,
            SIDEBAR_WIDTH - 40,
            item_height - 8,
        )
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

    if game.is_completed():
        draw_complete_screen(renderer=renderer, text=text, game=game)
        sdl2.SDL_RenderPresent(renderer)
        return

    stage = game.current_stage()

    draw_stage_text(text=text, stage=stage)
    draw_controls(text=text, builder=builder)
    draw_template_list(text=text, stage=stage, builder=builder)

    if stage.lanes:
        draw_swimlanes(renderer=renderer, text=text, stage=stage)

    draw_edges(renderer=renderer, text=text, builder=builder, stage=stage)
    draw_nodes(renderer=renderer, text=text, builder=builder)
    draw_messages(text=text, builder=builder)

    sdl2.SDL_RenderPresent(renderer)


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
    sidebar = sdl2.SDL_Rect(0, 0, SIDEBAR_WIDTH, WINDOW_HEIGHT)
    set_color(renderer, PANEL_COLOR)
    sdl2.SDL_RenderFillRect(renderer, sidebar)
    set_color(renderer, PANEL_BORDER)
    sdl2.SDL_RenderDrawRect(renderer, sidebar)


def draw_header(renderer: ctypes.c_void_p) -> None:
    header = sdl2.SDL_Rect(
        SIDEBAR_WIDTH,
        0,
        WINDOW_WIDTH - SIDEBAR_WIDTH,
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

    text.wrap_draw(
        text=f"Task: {stage.description}",
        x=left,
        y=top + 66,
        width=WINDOW_WIDTH - SIDEBAR_WIDTH - 60,
        color=SUBTEXT_COLOR,
        size=16,
    )


def draw_controls(text: TextRenderer, builder: BuilderState) -> None:
    x = 24
    y = 18

    text.draw("Controls", x, y, color=ACCENT, size=22)
    text.draw("Left click: select/place/drag", x, y + 34, color=SUBTEXT_COLOR, size=15)
    text.draw("Right click node: remove", x, y + 54, color=SUBTEXT_COLOR, size=15)
    text.draw(
        "Tab: edge mode   Enter: validate",
        x,
        y + 74,
        color=SUBTEXT_COLOR,
        size=15,
    )
    text.draw("X: undo edge   R: clear stage", x, y + 94, color=SUBTEXT_COLOR, size=15)
    text.draw("Grid snap + 90° auto-routing", x, y + 114, color=SUBTEXT_COLOR, size=15)

    mode_text = "Mode: EDGE" if builder.edge_mode else "Mode: MOVE"
    mode_color = ACCENT if builder.edge_mode else SUBTEXT_COLOR
    text.draw(mode_text, x, y + 136, color=mode_color, size=16)


def draw_template_list(text: TextRenderer, stage: Stage, builder: BuilderState) -> None:
    left = 24
    top = HEADER_HEIGHT + 36
    item_height = 68

    text.draw("Available Blocks", left, top - 28, color=ACCENT, size=20)

    for index, node in enumerate(stage.expected_nodes):
        item_top = top + index * item_height
        is_placed = node.node_id in builder.placed_nodes
        is_selected = builder.selected_template == node.node_id

        box = sdl2.SDL_Rect(left - 4, item_top - 4, SIDEBAR_WIDTH - 36, item_height - 8)
        color = (26, 30, 40, 255)
        if is_selected:
            color = (45, 62, 88, 255)
        elif is_placed:
            color = (35, 58, 50, 255)

        set_color(text.renderer, color)
        sdl2.SDL_RenderFillRect(text.renderer, box)
        set_color(text.renderer, PANEL_BORDER)
        sdl2.SDL_RenderDrawRect(text.renderer, box)

        text.draw(node.node_id, left + 8, item_top + 6, color=TEXT_COLOR, size=15)
        text.draw(
            f"{node.block_type.value} | {node.label}",
            left + 8,
            item_top + 28,
            color=SUBTEXT_COLOR,
            size=14,
        )


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

        set_color(renderer, NODE_FILL)
        if placed.template.block_type.value == "decision":
            draw_diamond_filled(renderer=renderer, rect=rect)
            set_color(renderer, NODE_BORDER)
            draw_diamond_outline(renderer=renderer, rect=rect)
        else:
            draw_rounded_rect_filled(renderer=renderer, rect=rect, radius=10)
            set_color(renderer, NODE_BORDER)
            draw_rounded_rect_outline(renderer=renderer, rect=rect, radius=10)

        cx, cy = placed.center
        text.draw(
            placed.template.label,
            cx - 56,
            cy - 10,
            color=TEXT_COLOR,
            size=16,
        )


def draw_edges(
    renderer: ctypes.c_void_p,
    text: TextRenderer,
    builder: BuilderState,
    stage: Stage,
) -> None:
    for edge in builder.edges:
        source_node = builder.placed_nodes.get(edge.source)
        target_node = builder.placed_nodes.get(edge.target)
        if source_node is None or target_node is None:
            continue

        path = route_edge_path(
            builder=builder,
            stage=stage,
            source=source_node,
            target=target_node,
        )
        if len(path) < 2:
            continue

        set_color(renderer, NODE_BORDER)
        for idx in range(len(path) - 1):
            sx, sy = path[idx]
            tx, ty = path[idx + 1]
            sdl2.SDL_RenderDrawLine(renderer, sx, sy, tx, ty)

        sx, sy = path[-2]
        tx, ty = path[-1]
        draw_arrow_head(renderer=renderer, sx=sx, sy=sy, tx=tx, ty=ty)

        if edge.label:
            mid_idx = len(path) // 2
            mx, my = path[mid_idx]
            mx += 8
            my -= 10
            text.draw(edge.label, mx, my, color=TEXT_COLOR, size=16)


def draw_messages(text: TextRenderer, builder: BuilderState) -> None:
    left = SIDEBAR_WIDTH + 30
    bottom = WINDOW_HEIGHT - 18

    for index, (message, color) in enumerate(reversed(builder.messages)):
        y = bottom - (index + 1) * 22
        text.draw(message, left, y, color=color, size=15)


def draw_complete_screen(
    renderer: ctypes.c_void_p,
    text: TextRenderer,
    game: FlowLearningGame,
) -> None:
    set_color(renderer, BG_COLOR)
    sdl2.SDL_RenderClear(renderer)

    text.draw("All stages completed", 420, 180, color=SUCCESS_COLOR, size=36)
    text.draw("Badges earned", 420, 235, color=ACCENT, size=24)

    start_y = 280
    for index, badge in enumerate(sorted(game.badges)):
        text.draw(f"- {badge}", 430, start_y + index * 28, color=TEXT_COLOR, size=18)

    text.draw(
        "Press R to restart or ESC to quit.",
        420,
        760,
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
    vx = tx - sx
    vy = ty - sy
    length = (vx * vx + vy * vy) ** 0.5
    if length < 1:
        return

    ux = vx / length
    uy = vy / length

    head_length = 14
    head_width = 8

    bx = tx - int(ux * head_length)
    by = ty - int(uy * head_length)

    left_x = bx + int(-uy * head_width)
    left_y = by + int(ux * head_width)
    right_x = bx - int(-uy * head_width)
    right_y = by - int(ux * head_width)

    sdl2.SDL_RenderDrawLine(renderer, tx, ty, left_x, left_y)
    sdl2.SDL_RenderDrawLine(renderer, tx, ty, right_x, right_y)


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


def route_edge_path(
    builder: BuilderState,
    stage: Stage,
    source: PlacedNode,
    target: PlacedNode,
) -> list[tuple[int, int]]:
    rect = canvas_rect()
    start = connector_point(source=source, toward=target.center)
    end = connector_point(source=target, toward=source.center)
    start = snap_point_to_grid(start[0], start[1], rect=rect)
    end = snap_point_to_grid(end[0], end[1], rect=rect)

    blocked = build_blocked_cells(
        builder=builder,
        stage=stage,
        ignore={source.template.node_id, target.template.node_id},
    )
    path = find_orthogonal_path(start=start, end=end, blocked=blocked, rect=rect)
    if not path:
        return [start, end]
    return compress_collinear(path)


def connector_point(source: PlacedNode, toward: tuple[int, int]) -> tuple[int, int]:
    rect = source.rect
    cx, cy = source.center
    tx, ty = toward
    dx = tx - cx
    dy = ty - cy

    if abs(dx) >= abs(dy):
        if dx >= 0:
            return (rect.x + rect.w, cy)
        return (rect.x, cy)

    if dy >= 0:
        return (cx, rect.y + rect.h)
    return (cx, rect.y)


def build_blocked_cells(
    builder: BuilderState,
    stage: Stage,
    ignore: set[str],
) -> set[tuple[int, int]]:
    del stage  # stage reserved for future lane-aware routing tweaks.
    rect = canvas_rect()
    blocked: set[tuple[int, int]] = set()

    for node_id, node in builder.placed_nodes.items():
        if node_id in ignore:
            continue
        node_rect = node.rect
        min_gx, min_gy = grid_from_pixel(node_rect.x - GRID_SIZE, node_rect.y - GRID_SIZE, rect)
        max_gx, max_gy = grid_from_pixel(
            node_rect.x + node_rect.w + GRID_SIZE,
            node_rect.y + node_rect.h + GRID_SIZE,
            rect,
        )
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
) -> list[tuple[int, int]]:
    start_g = grid_from_pixel(start[0], start[1], rect)
    end_g = grid_from_pixel(end[0], end[1], rect)

    open_heap: list[tuple[int, int, tuple[int, int]]] = []
    heapq.heappush(open_heap, (0, 0, start_g))

    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score = {start_g: 0}
    visited: set[tuple[int, int]] = set()

    while open_heap:
        _, cost, current = heapq.heappop(open_heap)
        if current in visited:
            continue
        visited.add(current)

        if current == end_g:
            return reconstruct_path(came_from, current, rect)

        cx, cy = current
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            neighbor = (nx, ny)
            if not in_grid_bounds(nx, ny, rect):
                continue
            if neighbor in blocked and neighbor != end_g:
                continue

            tentative_g = cost + 1
            if tentative_g >= g_score.get(neighbor, 10**9):
                continue

            came_from[neighbor] = current
            g_score[neighbor] = tentative_g
            h = abs(end_g[0] - nx) + abs(end_g[1] - ny)
            heapq.heappush(open_heap, (tentative_g + h, tentative_g, neighbor))

    return []


def reconstruct_path(
    came_from: dict[tuple[int, int], tuple[int, int]],
    current: tuple[int, int],
    rect: sdl2.SDL_Rect,
) -> list[tuple[int, int]]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return [pixel_from_grid(gx, gy, rect) for gx, gy in path]


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

    min_x = rect.x + 8
    max_x = rect.x + rect.w - width - 8
    min_y = rect.y + 8
    max_y = rect.y + rect.h - height - 8

    clamped_x = max(min_x, min(x, max_x))
    clamped_y = max(min_y, min(y, max_y))

    if not stage.lanes:
        snapped_x, snapped_y = snap_point_to_grid(clamped_x, clamped_y, rect=rect)
        return (
            max(min_x, min(snapped_x, max_x)),
            max(min_y, min(snapped_y, max_y)),
        )

    target_lane = node.template.lane
    lane_height = rect.h // len(stage.lanes)
    lane_index = stage.lanes.index(target_lane)

    lane_min_y = rect.y + lane_index * lane_height + 6
    lane_max_y = rect.y + (lane_index + 1) * lane_height - height - 6
    clamped_y = max(lane_min_y, min(clamped_y, lane_max_y))
    snapped_x, snapped_y = snap_point_to_grid(clamped_x, clamped_y, rect=rect)
    return (
        max(min_x, min(snapped_x, max_x)),
        max(lane_min_y, min(snapped_y, lane_max_y)),
    )


def lane_from_position(stage: Stage, y: int, rect: sdl2.SDL_Rect) -> str:
    lane_height = rect.h / len(stage.lanes)
    index = int((y - rect.y) / lane_height)
    index = max(0, min(index, len(stage.lanes) - 1))
    return stage.lanes[index]


def canvas_rect() -> sdl2.SDL_Rect:
    return sdl2.SDL_Rect(
        SIDEBAR_WIDTH + CANVAS_MARGIN,
        HEADER_HEIGHT + CANVAS_MARGIN,
        WINDOW_WIDTH - SIDEBAR_WIDTH - (2 * CANVAS_MARGIN),
        WINDOW_HEIGHT - HEADER_HEIGHT - (2 * CANVAS_MARGIN),
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


def in_grid_bounds(gx: int, gy: int, rect: sdl2.SDL_Rect) -> bool:
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
