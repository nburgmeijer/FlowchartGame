from flow_game.game import (
    BlockType,
    FlowLearningGame,
    parse_edge_line,
    parse_node_line,
)


def test_parse_node_line_with_lane() -> None:
    node = parse_node_line("read;process;Read input;Controller")

    assert node.node_id == "READ"
    assert node.block_type == BlockType.PROCESS
    assert node.label == "Read input"
    assert node.lane == "Controller"


def test_parse_edge_line_with_label() -> None:
    edge = parse_edge_line("valid->open;yes")

    assert edge.source == "VALID"
    assert edge.target == "OPEN"
    assert edge.label == "yes"


def test_wrong_edge_fails_without_advancing_stage() -> None:
    game = FlowLearningGame()
    stage = game.current_stage()

    wrong_edges = tuple(
        edge for edge in stage.expected_edges if edge.source != "WAIT_2"
    )

    result = game.submit_current_stage(stage.expected_nodes, wrong_edges)

    assert not result.passed
    assert any("Missing required edges" in error for error in result.errors)
    assert game.current_stage_index == 0


def test_stage_completion_awards_stage_badge_and_advances() -> None:
    game = FlowLearningGame()
    stage = game.current_stage()

    result = game.submit_current_stage(stage.expected_nodes, stage.expected_edges)

    assert result.passed
    assert stage.badge_name in result.earned_badges
    assert game.current_stage_index == 1


def test_first_try_badge_only_when_stage_passes_on_first_attempt() -> None:
    game = FlowLearningGame()
    stage = game.current_stage()

    wrong_edges = tuple(
        edge for edge in stage.expected_edges if edge.source != "WAIT_2"
    )
    failed = game.submit_current_stage(stage.expected_nodes, wrong_edges)
    passed = game.submit_current_stage(stage.expected_nodes, stage.expected_edges)

    assert not failed.passed
    assert passed.passed
    assert all(
        not badge.startswith("First Try:")
        for badge in passed.earned_badges
    )


def test_finishing_all_stages_awards_flow_architect() -> None:
    game = FlowLearningGame()

    while not game.is_completed():
        stage = game.current_stage()
        result = game.submit_current_stage(stage.expected_nodes, stage.expected_edges)
        assert result.passed

    assert "Flow Architect" in game.badges
