import sys


def _dispatch(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--auto" in argv:
        argv.remove("--auto")
        from omelet.placement.autoplace import main as auto_main
        return auto_main(argv)
    from omelet.placement.engine import main as engine_main
    return engine_main(argv)


if __name__ == "__main__":
    raise SystemExit(_dispatch())
