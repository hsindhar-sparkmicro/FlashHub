#!/usr/bin/env python3
"""
FlashHub CLI — flash / reset / inspect probes without a GUI.

Usage examples
--------------
  # Show all configured projects and their aliases
  python cli.py list-projects

  # Switch active project
  python cli.py use-project "Ranging MAMT"

  # List currently connected probes (with alias lookup)
  python cli.py list-probes

  # Flash a single probe by its alias
  python cli.py flash --probe Anchor

  # Flash with a one-off firmware override
  python cli.py flash --probe TAG --firmware /path/to/other.bin

  # Flash all connected probes in the current project
  python cli.py flash-all

  # Flash all probes in a *different* project (without switching)
  python cli.py flash-all --project "IDP-Simran"

  # Reset a probe
  python cli.py reset --probe Anchor

  # Auto-detect MCU on a probe
  python cli.py detect-target --probe TAG

  # List every pyocd-supported target name
  python cli.py list-targets
"""

import argparse
import sys
import os

# Ensure project root is on sys.path when script is run directly
sys.path.insert(0, os.path.dirname(__file__))

from src.utils.config_manager import ConfigManager
from src.cli.commands import (
    cmd_list_projects,
    cmd_use_project,
    cmd_list_probes,
    cmd_flash,
    cmd_flash_all,
    cmd_reset,
    cmd_detect_target,
    cmd_list_targets,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flashhub",
        description="FlashHub CLI — alias-based firmware flashing",
    )
    parser.add_argument(
        "--config",
        default="config.json",
        metavar="FILE",
        help="Path to config.json (default: config.json in cwd)",
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # ---- list-projects -------------------------------------------------------
    sub.add_parser("list-projects", help="Show all projects and their probe aliases")

    # ---- use-project ---------------------------------------------------------
    p = sub.add_parser("use-project", help="Set the active project by name")
    p.add_argument("name", help="Project name (quote if it contains spaces)")

    # ---- list-probes ---------------------------------------------------------
    p = sub.add_parser("list-probes", help="List connected probes with alias info")
    p.add_argument("--project", metavar="NAME", help="Use this project instead of the active one")

    # ---- flash ---------------------------------------------------------------
    p = sub.add_parser("flash", help="Flash a single probe by alias")
    p.add_argument("--probe", required=True, metavar="ALIAS", help="Probe alias (e.g. Anchor, TAG)")
    p.add_argument("--firmware", metavar="FILE", help="Override firmware path for this run")
    p.add_argument("--project", metavar="NAME", help="Use this project instead of the active one")

    # ---- flash-all -----------------------------------------------------------
    p = sub.add_parser("flash-all", help="Flash all configured probes in a project")
    p.add_argument("--project", metavar="NAME", help="Use this project instead of the active one")

    # ---- reset ---------------------------------------------------------------
    p = sub.add_parser("reset", help="Reset a probe's MCU without flashing")
    p.add_argument("--probe", required=True, metavar="ALIAS", help="Probe alias")
    p.add_argument("--project", metavar="NAME", help="Use this project instead of the active one")

    # ---- detect-target -------------------------------------------------------
    p = sub.add_parser("detect-target", help="Auto-detect the MCU on a probe")
    p.add_argument("--probe", required=True, metavar="ALIAS", help="Probe alias")
    p.add_argument("--project", metavar="NAME", help="Use this project instead of the active one")

    # ---- list-targets --------------------------------------------------------
    sub.add_parser("list-targets", help="List all pyocd-supported target names")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    cfg = ConfigManager(config_path=args.config)

    match args.command:
        case "list-projects":
            cmd_list_projects(cfg)

        case "use-project":
            cmd_use_project(cfg, args.name)

        case "list-probes":
            cmd_list_probes(cfg, getattr(args, "project", None))

        case "flash":
            cmd_flash(cfg, args.probe, getattr(args, "project", None), getattr(args, "firmware", None))

        case "flash-all":
            cmd_flash_all(cfg, getattr(args, "project", None))

        case "reset":
            cmd_reset(cfg, args.probe, getattr(args, "project", None))

        case "detect-target":
            cmd_detect_target(cfg, args.probe, getattr(args, "project", None))

        case "list-targets":
            cmd_list_targets()

        case _:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()
