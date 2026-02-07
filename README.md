# Flow Diagram Learning Game

A 2D SDL2 educational game for learning flow diagrams step by step.

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
make setup-sdl2
make run
```

If SDL2 is not available on your machine, the app falls back to the terminal version.

If you get `No module named sdl2` or SDL2 load errors, install system libs:

- macOS (Homebrew): `brew install sdl2 sdl2_ttf`
- Ubuntu/Debian: `sudo apt install libsdl2-2.0-0 libsdl2-ttf-2.0-0`

## SDL2 Controls

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
- `make setup-sdl2` - install project + dev + SDL2 extras.
- `make run` - launch the SDL2 game.
- `make test` - run tests.
- `make lint` - run Ruff checks.
- `make format` - auto-format imports/code with Ruff.
