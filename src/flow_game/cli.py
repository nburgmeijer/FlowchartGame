from __future__ import annotations

from .game import (
    DiagramEdge,
    DiagramNode,
    FlowLearningGame,
    parse_edge_line,
    parse_node_line,
)


def main() -> None:
    game = FlowLearningGame()

    print("Flow Diagram Learning Game")
    print("Build diagrams from written system tasks and earn badges.\n")

    while not game.is_completed():
        stage = game.current_stage()
        print(f"{stage.title}")
        print(f"Task: {stage.description}")
        print(f"Learning goal: {stage.learning_goal}")
        if stage.lanes:
            print(f"Required swimlanes: {', '.join(stage.lanes)}")

        print("\nNode format: NODE_ID;block_type;label[;lane]")
        print("Block types: start_end, process, decision")
        print("Edge format: SOURCE->TARGET[;label]")
        print("Press Enter on an empty line to finish each section.")
        print("Type 'quit' at any input prompt to exit.")

        nodes = collect_nodes()
        if nodes is None:
            print("Exiting game.")
            return

        edges = collect_edges()
        if edges is None:
            print("Exiting game.")
            return

        result = game.submit_current_stage(nodes=nodes, edges=edges)

        if result.passed:
            print("\nCorrect diagram.")
            for badge in result.earned_badges:
                print(f"Earned badge: {badge}")

            if result.game_completed:
                print("\nYou completed all stages.")
            else:
                print("Next stage unlocked.\n")
        else:
            print("\nNot correct yet:")
            for error in result.errors:
                print(f"- {error}")
            print(f"Hint: {stage.hint}\n")

    print("All badges:")
    for badge in sorted(game.badges):
        print(f"- {badge}")


def collect_nodes() -> tuple[DiagramNode, ...] | None:
    print("\nEnter nodes:")
    lines = collect_section_lines()
    if lines is None:
        return None

    nodes: list[DiagramNode] = []
    for line in lines:
        try:
            nodes.append(parse_node_line(line))
        except ValueError as exc:
            print(f"Node parse error: {exc}")
            return collect_nodes()
    return tuple(nodes)


def collect_edges() -> tuple[DiagramEdge, ...] | None:
    print("\nEnter edges:")
    lines = collect_section_lines()
    if lines is None:
        return None

    edges: list[DiagramEdge] = []
    for line in lines:
        try:
            edges.append(parse_edge_line(line))
        except ValueError as exc:
            print(f"Edge parse error: {exc}")
            return collect_edges()
    return tuple(edges)


def collect_section_lines() -> list[str] | None:
    lines: list[str] = []
    while True:
        entry = input("> ").strip()
        if entry.lower() == "quit":
            return None
        if not entry:
            return lines
        lines.append(entry)


if __name__ == "__main__":
    main()
