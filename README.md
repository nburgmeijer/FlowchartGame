# Flow Diagram Learning Game

A 2D SDL3 educational game for learning flow diagrams step by step.

You get written system tasks, place flowchart blocks on a canvas, connect them with arrows, and validate your solution. Correct diagrams unlock the next stage and award motivational badges.

## Learning progression

1. Block basics (start/process loop)
2. Decision branching (yes/no paths)
3. Thermostat control loop (based on the provided visual style)
4. Swimlanes (User vs Controller responsibilities)

## Quickstart

```bash
python3.14 -m venv .venv
source .venv/bin/activate
make setup-sdl3
make run
```

If SDL3 is not available on your machine, the app falls back to the terminal version.

If you get `No module named sdl3` or SDL3 load errors, install system libs:

- macOS (Homebrew): `brew install sdl3 sdl3_ttf`
- Ubuntu/Debian: `sudo apt install libsdl3-0 libsdl3-ttf-0`

## SDL3 Controls

- Left click a block in the sidebar, then left click canvas to place it
- Left click and drag to move a placed block
- Right click a placed block to remove it
- `Tab`: toggle edge mode
- In edge mode: left click source node, then target node to create an arrow
- `X`: remove last edge
- `Enter`: validate current stage
- `R`: clear current stage workspace
- `Esc`: quit

## Commands

- `make setup` - install project + dev dependencies.
- `make setup-sdl3` - install project + dev + SDL3 extras.
- `make run` - launch the SDL3 game.
- `make test` - run tests.
- `make lint` - run Ruff checks.
- `make format` - auto-format imports/code with Ruff.
