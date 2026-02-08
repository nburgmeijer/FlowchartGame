from __future__ import annotations

from flow_game.game import BlockType, DiagramNode, Stage
from flow_game.sdl3_game import (
    BuilderState,
    BuiltEdge,
    PlacedNode,
    canvas_rect,
    grid_from_pixel,
    route_all_edge_paths,
)


def test_staged_two_edge_routing_order_is_deterministic() -> None:
    """Cover staged 2-edge routing order used during manual UI validation."""
    stage = Stage(
        stage_id="deterministic",
        title="Deterministic",
        description="",
        learning_goal="",
        hint="",
        badge_name="",
        expected_nodes=tuple(),
        expected_edges=tuple(),
        lanes=tuple(),
    )
    rect = canvas_rect()

    x0, y0, step = (520, 280, 110)
    nodes = {
        "start": PlacedNode(
            DiagramNode("start", BlockType.START_END, "Start"),
            x0,
            y0,
        ),
        "led_on": PlacedNode(
            DiagramNode("led_on", BlockType.PROCESS, "LED on"),
            x0,
            y0 + step,
        ),
        "wait_1": PlacedNode(
            DiagramNode("wait_1", BlockType.PROCESS, "Wait 1 second"),
            x0,
            y0 + (2 * step),
        ),
    }
    edges = [
        BuiltEdge("start", "wait_1", "", 3, 3),
        BuiltEdge("start", "led_on", "", 1, 1),
    ]
    builder = BuilderState(placed_nodes=nodes, edges=edges)

    routed = route_all_edge_paths(builder=builder, stage=stage)
    routed_cells = {
        (edge.source, edge.target): [grid_from_pixel(x, y, rect) for x, y in path]
        for edge, path in routed
    }

    assert routed_cells[("start", "wait_1")] == [
        (3, 6),
        (2, 6),
        (2, 6),
        (1, 6),
        (1, 16),
        (3, 16),
        (3, 16),
    ]
    assert routed_cells[("start", "led_on")] == [
        (9, 6),
        (10, 6),
        (10, 6),
        (11, 6),
        (11, 11),
        (9, 11),
        (9, 11),
    ]
