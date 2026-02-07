from .cli import main as cli_main


def main() -> None:
    try:
        from .sdl2_game import main as sdl2_main
    except Exception as exc:  # pragma: no cover - runtime fallback
        print(f"SDL2 mode unavailable: {exc}")
        print("Falling back to terminal mode.")
        cli_main()
        return

    sdl2_main()


if __name__ == "__main__":
    main()
