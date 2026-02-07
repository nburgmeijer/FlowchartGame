from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BlockType(str, Enum):
    START_END = "start_end"
    PROCESS = "process"
    DECISION = "decision"


@dataclass(frozen=True)
class DiagramNode:
    node_id: str
    block_type: BlockType
    label: str
    lane: str = ""


@dataclass(frozen=True)
class DiagramEdge:
    source: str
    target: str
    label: str = ""


@dataclass(frozen=True)
class Stage:
    stage_id: str
    title: str
    description: str
    learning_goal: str
    hint: str
    badge_name: str
    expected_nodes: tuple[DiagramNode, ...]
    expected_edges: tuple[DiagramEdge, ...]
    lanes: tuple[str, ...] = tuple()


@dataclass(frozen=True)
class StageAttemptResult:
    passed: bool
    errors: tuple[str, ...]
    earned_badges: tuple[str, ...]
    next_stage_unlocked: bool
    game_completed: bool


@dataclass
class FlowLearningGame:
    stages: tuple[Stage, ...] = field(default_factory=lambda: default_stages())
    current_stage_index: int = 0
    badges: set[str] = field(default_factory=set)
    attempts_by_stage: dict[str, int] = field(default_factory=dict)

    def current_stage(self) -> Stage:
        return self.stages[self.current_stage_index]

    def is_completed(self) -> bool:
        return self.current_stage_index >= len(self.stages)

    def submit_current_stage(
        self, nodes: tuple[DiagramNode, ...], edges: tuple[DiagramEdge, ...]
    ) -> StageAttemptResult:
        if self.is_completed():
            return StageAttemptResult(
                passed=False,
                errors=("All stages are already complete.",),
                earned_badges=tuple(),
                next_stage_unlocked=False,
                game_completed=True,
            )

        stage = self.current_stage()
        stage_id = stage.stage_id
        self.attempts_by_stage[stage_id] = self.attempts_by_stage.get(stage_id, 0) + 1

        errors = validate_diagram(stage, nodes, edges)
        if errors:
            return StageAttemptResult(
                passed=False,
                errors=errors,
                earned_badges=tuple(),
                next_stage_unlocked=False,
                game_completed=False,
            )

        earned_badges: list[str] = []
        if stage.badge_name not in self.badges:
            self.badges.add(stage.badge_name)
            earned_badges.append(stage.badge_name)

        if self.attempts_by_stage[stage_id] == 1:
            first_try_badge = f"First Try: {stage.title}"
            if first_try_badge not in self.badges:
                self.badges.add(first_try_badge)
                earned_badges.append(first_try_badge)

        self.current_stage_index += 1
        game_completed = self.is_completed()
        if game_completed:
            mastery_badge = "Flow Architect"
            if mastery_badge not in self.badges:
                self.badges.add(mastery_badge)
                earned_badges.append(mastery_badge)

        return StageAttemptResult(
            passed=True,
            errors=tuple(),
            earned_badges=tuple(earned_badges),
            next_stage_unlocked=not game_completed,
            game_completed=game_completed,
        )


def parse_node_line(line: str) -> DiagramNode:
    """Parse `NODE_ID;block_type;label[;lane]`."""
    parts = [part.strip() for part in line.split(";")]
    if len(parts) not in (3, 4):
        raise ValueError(
            "Node must use format NODE_ID;block_type;label[;lane]."
        )

    node_id = normalize_id(parts[0])
    block_type_text = normalize_text(parts[1])
    label = parts[2].strip()
    lane = parts[3].strip() if len(parts) == 4 else ""

    if not node_id:
        raise ValueError("Node id cannot be empty.")
    if not label:
        raise ValueError("Node label cannot be empty.")

    try:
        block_type = BlockType(block_type_text)
    except ValueError as exc:
        raise ValueError(
            "Block type must be one of: start_end, process, decision."
        ) from exc

    return DiagramNode(node_id=node_id, block_type=block_type, label=label, lane=lane)


def parse_edge_line(line: str) -> DiagramEdge:
    """Parse `SOURCE->TARGET[;label]`."""
    raw, *label_parts = [part.strip() for part in line.split(";")]
    label = label_parts[0] if label_parts else ""
    if len(label_parts) > 1:
        raise ValueError("Edge supports at most one optional ';label' section.")

    if "->" not in raw:
        raise ValueError("Edge must use format SOURCE->TARGET[;label].")

    source_raw, target_raw = [part.strip() for part in raw.split("->", maxsplit=1)]
    source = normalize_id(source_raw)
    target = normalize_id(target_raw)

    if not source or not target:
        raise ValueError("Edge source and target cannot be empty.")

    return DiagramEdge(source=source, target=target, label=label)


def validate_diagram(
    stage: Stage, nodes: tuple[DiagramNode, ...], edges: tuple[DiagramEdge, ...]
) -> tuple[str, ...]:
    errors: list[str] = []

    expected_nodes_by_id = {node.node_id: node for node in stage.expected_nodes}
    submitted_nodes_by_id: dict[str, DiagramNode] = {}

    for node in nodes:
        if node.node_id in submitted_nodes_by_id:
            errors.append(f"Duplicate node id: {node.node_id}.")
        submitted_nodes_by_id[node.node_id] = node

    expected_ids = set(expected_nodes_by_id)
    submitted_ids = set(submitted_nodes_by_id)

    missing_ids = sorted(expected_ids - submitted_ids)
    extra_ids = sorted(submitted_ids - expected_ids)

    if missing_ids:
        errors.append(f"Missing required node ids: {', '.join(missing_ids)}.")
    if extra_ids:
        errors.append(f"Unknown node ids: {', '.join(extra_ids)}.")

    for node_id in sorted(expected_ids & submitted_ids):
        expected = expected_nodes_by_id[node_id]
        actual = submitted_nodes_by_id[node_id]

        if actual.block_type is not expected.block_type:
            errors.append(
                f"Node {node_id} has block type {actual.block_type.value}; "
                f"expected {expected.block_type.value}."
            )
        if normalize_text(actual.label) != normalize_text(expected.label):
            errors.append(
                f"Node {node_id} has label '{actual.label}'; "
                f"expected '{expected.label}'."
            )

        if stage.lanes:
            if normalize_text(actual.lane) != normalize_text(expected.lane):
                errors.append(
                    f"Node {node_id} must be in lane '{expected.lane}'."
                )

    normalized_submitted_edges = {
        (
            edge.source,
            edge.target,
            normalize_text(edge.label),
        )
        for edge in edges
    }
    normalized_expected_edges = {
        (
            edge.source,
            edge.target,
            normalize_text(edge.label),
        )
        for edge in stage.expected_edges
    }

    missing_edges = sorted(normalized_expected_edges - normalized_submitted_edges)
    extra_edges = sorted(normalized_submitted_edges - normalized_expected_edges)

    if missing_edges:
        errors.append(
            "Missing required edges: "
            + ", ".join(format_edge(edge) for edge in missing_edges)
            + "."
        )
    if extra_edges:
        errors.append(
            "Unexpected edges: "
            + ", ".join(format_edge(edge) for edge in extra_edges)
            + "."
        )

    return tuple(errors)


def format_edge(edge: tuple[str, str, str]) -> str:
    source, target, label = edge
    if label:
        return f"{source}->{target};{label}"
    return f"{source}->{target}"


def normalize_id(text: str) -> str:
    return text.strip().upper().replace(" ", "_")


def normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def default_stages() -> tuple[Stage, ...]:
    return (
        Stage(
            stage_id="stage_1",
            title="Stage 1: Block Basics",
            description=(
                "System task: one LED blinks on/off every second forever. "
                "Build a loop with start and process blocks."
            ),
            learning_goal="Understand start/end and process block sequencing.",
            hint="You need a loop from the final wait node back to LED on.",
            badge_name="Badge: Blink Builder",
            expected_nodes=(
                DiagramNode("START", BlockType.START_END, "Start"),
                DiagramNode("LED_ON", BlockType.PROCESS, "LED on"),
                DiagramNode("WAIT_1", BlockType.PROCESS, "Wait 1 second"),
                DiagramNode("LED_OFF", BlockType.PROCESS, "LED off"),
                DiagramNode("WAIT_2", BlockType.PROCESS, "Wait 1 second"),
            ),
            expected_edges=(
                DiagramEdge("START", "LED_ON"),
                DiagramEdge("LED_ON", "WAIT_1"),
                DiagramEdge("WAIT_1", "LED_OFF"),
                DiagramEdge("LED_OFF", "WAIT_2"),
                DiagramEdge("WAIT_2", "LED_ON"),
            ),
        ),
        Stage(
            stage_id="stage_2",
            title="Stage 2: Decision Branching",
            description=(
                "System task: read temperature and decide fan state. "
                "If temperature > 25 C, turn fan on; otherwise fan off; "
                "then measure again."
            ),
            learning_goal="Use a decision block with yes/no outgoing paths.",
            hint="The decision node should branch to two actions labeled yes and no.",
            badge_name="Badge: Branch Navigator",
            expected_nodes=(
                DiagramNode("START", BlockType.START_END, "Start"),
                DiagramNode("MEASURE", BlockType.PROCESS, "Measure temperature"),
                DiagramNode("HOT", BlockType.DECISION, "Temperature > 25 C?"),
                DiagramNode("FAN_ON", BlockType.PROCESS, "Fan on"),
                DiagramNode("FAN_OFF", BlockType.PROCESS, "Fan off"),
            ),
            expected_edges=(
                DiagramEdge("START", "MEASURE"),
                DiagramEdge("MEASURE", "HOT"),
                DiagramEdge("HOT", "FAN_ON", "yes"),
                DiagramEdge("HOT", "FAN_OFF", "no"),
                DiagramEdge("FAN_ON", "MEASURE"),
                DiagramEdge("FAN_OFF", "MEASURE"),
            ),
        ),
        Stage(
            stage_id="stage_3",
            title="Stage 3: Thermostat Loop",
            description=(
                "System task: like the reference thermostat diagram. "
                "Measure temperature, check T > 20 C, and toggle heating "
                "with a loop back."
            ),
            learning_goal="Model a full control loop from measurement to action.",
            hint="Both heating states should return to the measurement step.",
            badge_name="Badge: Control Loop Crafter",
            expected_nodes=(
                DiagramNode("START", BlockType.START_END, "Start"),
                DiagramNode("MEASURE_TEMP", BlockType.PROCESS, "Meet temperatuur"),
                DiagramNode("ABOVE_20", BlockType.DECISION, "T > 20 C"),
                DiagramNode("HEATING_OFF", BlockType.PROCESS, "Verwarming uit"),
                DiagramNode("HEATING_ON", BlockType.PROCESS, "Verwarming aan"),
            ),
            expected_edges=(
                DiagramEdge("START", "MEASURE_TEMP"),
                DiagramEdge("MEASURE_TEMP", "ABOVE_20"),
                DiagramEdge("ABOVE_20", "HEATING_OFF", "ja"),
                DiagramEdge("ABOVE_20", "HEATING_ON", "nee"),
                DiagramEdge("HEATING_OFF", "MEASURE_TEMP"),
                DiagramEdge("HEATING_ON", "MEASURE_TEMP"),
            ),
        ),
        Stage(
            stage_id="stage_4",
            title="Stage 4: Swimlanes",
            description=(
                "System task: automatic door request split across lanes. "
                "User presses button; controller validates and opens door "
                "or shows error."
            ),
            learning_goal=(
                "Place nodes in correct swimlanes without over-complicating "
                "logic."
            ),
            hint="Use two lanes: User and Controller.",
            badge_name="Badge: Swimlane Starter",
            lanes=("User", "Controller"),
            expected_nodes=(
                DiagramNode("START", BlockType.START_END, "Start", "User"),
                DiagramNode("PRESS", BlockType.PROCESS, "Press button", "User"),
                DiagramNode("READ", BlockType.PROCESS, "Read input", "Controller"),
                DiagramNode(
                    "VALID",
                    BlockType.DECISION,
                    "Request valid?",
                    "Controller",
                ),
                DiagramNode("OPEN", BlockType.PROCESS, "Open door", "Controller"),
                DiagramNode("ERROR", BlockType.PROCESS, "Show error", "Controller"),
                DiagramNode("END", BlockType.START_END, "End", "User"),
            ),
            expected_edges=(
                DiagramEdge("START", "PRESS"),
                DiagramEdge("PRESS", "READ"),
                DiagramEdge("READ", "VALID"),
                DiagramEdge("VALID", "OPEN", "yes"),
                DiagramEdge("VALID", "ERROR", "no"),
                DiagramEdge("OPEN", "END"),
                DiagramEdge("ERROR", "END"),
            ),
        ),
    )
