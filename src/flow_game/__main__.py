from .cli import main as cli_main


def main() -> None:
    try:
        from .sdl3_game import main as sdl_main
    except Exception as exc:  # pragma: no cover - runtime fallback
        print(f"SDL mode unavailable: {exc}")
        print("Falling back to terminal mode.")
        cli_main()
        return

    sdl_main()


if __name__ == "__main__":
    main()
