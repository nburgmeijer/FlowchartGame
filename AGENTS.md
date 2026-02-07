# Repository Guidelines

## Project Structure & Module Organization
The game code lives in `src/flow_game/`.
- `src/flow_game/game.py`: core game state and rules
- `src/flow_game/cli.py`: terminal interface loop
- `src/flow_game/__main__.py`: module entry point (`python3 -m flow_game`)
- `tests/`: unit tests for gameplay logic
- `assets/`: placeholder for art/audio/data files
- `docs/`: design or architecture notes

Keep gameplay rules in `game.py` and keep I/O in `cli.py` so logic stays testable.

## Build, Test, and Development Commands
Use Python 3.14+.
- `python3.14 -m venv .venv && source .venv/bin/activate`: create and activate local environment
- `pip install -e .[dev]`: install package plus dev tooling
- `make run`: launch the terminal game
- `make test`: run `pytest`
- `make lint`: run Ruff lint checks
- `make format`: apply Ruff auto-fixes

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation.
- Use type hints for public functions and methods.
- Modules/files: `snake_case.py`; classes: `PascalCase`; variables/functions: `snake_case`.
- Keep functions focused and side effects explicit.
- Run linting before opening a PR.

## Testing Guidelines
- Framework: `pytest`.
- Place tests in `tests/` and name files `test_*.py`.
- Name tests by behavior (example: `test_dead_end_results_in_loss`).
- Add tests for every new rule, bug fix, or edge case.
- Prioritize deterministic unit tests over interactive CLI tests.

## Commit & Pull Request Guidelines
Adopt Conventional Commits:
- `feat: add alternate level graph`
- `fix: prevent moves after game over`
- `test: cover invalid transition handling`

PRs should include:
- short problem/solution summary
- linked issue (if available)
- test evidence (`make test` output)
- terminal screenshots/GIFs for CLI UX changes

## Security & Configuration Tips
Do not commit secrets or machine-specific files. Keep environment-specific settings in local `.env` files and provide `.env.example` only when needed.

## Dependency Packaging Rule
- Any new runtime dependency must be packaged for distribution builds, including GitHub Actions artifacts.
- For Windows artifacts:
  - Update `.github/workflows/windows-exe.yml` and `.github/workflows/windows-arm-exe.yml` so the dependency binaries/data are bundled.
  - Do not rely on target machines to have dependency libraries preinstalled.
- For architecture-specific builds (for example Windows ARM64):
  - Always prefer architecture-native dependency binaries/wheels first.
  - Fail early in CI when a dependency has no payload for the target architecture.
  - Only use fallback download logic when no architecture-native package is available, and keep that fallback explicit in workflow logs.
- Any non-stdlib import that can be missing at runtime must use an import guard pattern:
  - wrap import in `try/except ModuleNotFoundError`
  - store the import error in a module-level variable
  - provide a deterministic fallback behavior or a clear runtime error message
- When adding a new dependency, update `pyproject.toml` and verify packaging changes in CI before merge.
