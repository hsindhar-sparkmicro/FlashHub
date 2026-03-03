"""
CLI command implementations for FlashHub.

All commands resolve probe aliases defined in config.json, so callers
never need to type a raw unique_id.

Probe alias → unique_id resolution is always scoped to the *active* project
(current_project_index) unless --project <name> is supplied.
"""

import sys
import logging
from src.utils.config_manager import ConfigManager
from src.backend.pyocd_wrapper import PyOCDWrapper

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_project(cfg: ConfigManager, project_name: str | None):
    """Return the project dict to operate on (by name or current)."""
    if project_name:
        for p in cfg.get_projects():
            if p["name"].lower() == project_name.lower():
                return p
        print(f"[error] Project '{project_name}' not found.", file=sys.stderr)
        sys.exit(1)
    proj = cfg.get_current_project()
    if proj is None:
        print("[error] No active project in config.json.", file=sys.stderr)
        sys.exit(1)
    return proj


def _resolve_alias(project: dict, alias: str) -> tuple[str, dict]:
    """
    Resolve a probe alias string to (unique_id, probe_cfg_dict).
    Matching is case-insensitive.
    Exits with an error message if not found.
    """
    probes_config: dict = project.get("probes_config", {})
    for uid, cfg in probes_config.items():
        if cfg.get("alias", "").lower() == alias.lower():
            return uid, cfg
    # List available aliases to help the user
    known = [c.get("alias", uid) for uid, c in probes_config.items()]
    print(
        f"[error] Alias '{alias}' not found in project '{project['name']}'.\n"
        f"        Known aliases: {', '.join(known) if known else '(none)'}",
        file=sys.stderr,
    )
    sys.exit(1)


def _connected_uid_set() -> set[str]:
    """Return set of unique_ids for currently connected probes (uppercase)."""
    return {p["unique_id"].upper() for p in PyOCDWrapper.list_probes()}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list_projects(cfg: ConfigManager):
    """Print all projects with their configured probe aliases."""
    projects = cfg.get_projects()
    active_idx = cfg.config.get("current_project_index", 0)

    if not projects:
        print("No projects configured.")
        return

    for i, proj in enumerate(projects):
        marker = " *" if i == active_idx else "  "
        print(f"{marker} [{i}] {proj['name']}  (target: {proj.get('target_device', '?')})")

        probes_config = proj.get("probes_config", {})
        if probes_config:
            for uid, pcfg in probes_config.items():
                alias = pcfg.get("alias") or uid
                fw = pcfg.get("firmware") or "(no firmware)"
                print(f"        alias: {alias:<20} uid: {uid}  fw: {fw}")
        else:
            print("        (no probes configured)")


def cmd_use_project(cfg: ConfigManager, project_name: str):
    """Switch the active project by name and persist the change."""
    for i, proj in enumerate(cfg.get_projects()):
        if proj["name"].lower() == project_name.lower():
            cfg.select_project(i)
            print(f"Active project is now: {proj['name']}")
            return
    print(f"[error] Project '{project_name}' not found.", file=sys.stderr)
    sys.exit(1)


def cmd_list_probes(cfg: ConfigManager, project_name: str | None):
    """
    List connected physical probes.
    If they match an alias in the active/specified project, show it.
    """
    proj = _get_project(cfg, project_name)
    probes_config: dict = proj.get("probes_config", {})
    connected = PyOCDWrapper.list_probes()

    if not connected:
        print("No probes connected.")
        return

    print(f"Connected probes  (project: {proj['name']}):")
    print(f"  {'Alias':<20} {'Vendor':<16} {'Product':<28} UID")
    print("  " + "-" * 90)
    for p in connected:
        uid = p["unique_id"].upper()
        # Find alias for this uid (case-insensitive key lookup)
        alias = next(
            (c.get("alias", "") for k, c in probes_config.items() if k.upper() == uid),
            "(unregistered)",
        )
        print(
            f"  {alias:<20} {p.get('vendor_name',''):<16} "
            f"{p.get('product_name',''):<28} {uid}"
        )


def cmd_flash(
    cfg: ConfigManager,
    alias: str,
    project_name: str | None,
    firmware_override: str | None,
):
    """Flash a probe identified by alias using its configured firmware."""
    proj = _get_project(cfg, project_name)
    uid, probe_cfg = _resolve_alias(proj, alias)
    target = proj.get("target_device")
    firmware = firmware_override or probe_cfg.get("firmware")

    if not target:
        print(f"[error] No target_device set for project '{proj['name']}'.", file=sys.stderr)
        sys.exit(1)
    if not firmware:
        print(
            f"[error] No firmware path configured for alias '{alias}'.\n"
            f"        Set one in config.json or pass --firmware <path>.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Verify the probe is actually connected
    if uid.upper() not in _connected_uid_set():
        print(f"[error] Probe '{alias}' (UID {uid}) is not connected.", file=sys.stderr)
        sys.exit(1)

    print(f"Flashing '{alias}'  target={target}  fw={firmware}")
    print(f"  UID: {uid}")
    if proj.get("packs"):
        print(f"  Packs: {', '.join(proj['packs'])}")

    def show_progress(pct: int):
        bar = "#" * (pct // 5)
        print(f"\r  [{bar:<20}] {pct:3d}%", end="", flush=True)

    try:
        PyOCDWrapper.flash_firmware(
            uid, target, firmware,
            progress_callback=show_progress,
            packs=proj.get("packs") or None,
        )
        print()  # newline after progress bar
        print(f"[ok] Flash complete for '{alias}'.")
    except Exception as e:
        print(f"\n[error] Flash failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_flash_all(
    cfg: ConfigManager,
    project_name: str | None,
):
    """Flash every probe configured in the project that is currently connected."""
    proj = _get_project(cfg, project_name)
    probes_config: dict = proj.get("probes_config", {})
    target = proj.get("target_device")
    connected = _connected_uid_set()

    if not probes_config:
        print(f"[error] No probes configured in project '{proj['name']}'.", file=sys.stderr)
        sys.exit(1)

    errors = []
    for uid, pcfg in probes_config.items():
        alias = pcfg.get("alias") or uid
        firmware = pcfg.get("firmware")

        if uid.upper() not in connected:
            print(f"  [skip] '{alias}' not connected.")
            continue
        if not firmware:
            print(f"  [skip] '{alias}' has no firmware configured.")
            continue

        print(f"\nFlashing '{alias}'  target={target}  fw={firmware}")

        def _progress(pct, _alias=alias):
            bar = "#" * (pct // 5)
            print(f"\r  [{bar:<20}] {pct:3d}%", end="", flush=True)

        try:
            PyOCDWrapper.flash_firmware(
                uid, target, firmware,
                progress_callback=_progress,
                packs=proj.get("packs") or None,
            )
            print()
            print(f"  [ok] '{alias}' done.")
        except Exception as e:
            print(f"\n  [fail] '{alias}': {e}", file=sys.stderr)
            errors.append(alias)

    if errors:
        print(f"\n[error] Failed probes: {', '.join(errors)}", file=sys.stderr)
        sys.exit(1)
    else:
        print("\n[ok] All probes flashed successfully.")


def cmd_reset(cfg: ConfigManager, alias: str, project_name: str | None):
    """Reset a probe's target MCU without flashing."""
    proj = _get_project(cfg, project_name)
    uid, _ = _resolve_alias(proj, alias)
    target = proj.get("target_device")

    if not target:
        print(f"[error] No target_device set for project '{proj['name']}'.", file=sys.stderr)
        sys.exit(1)
    if uid.upper() not in _connected_uid_set():
        print(f"[error] Probe '{alias}' (UID {uid}) is not connected.", file=sys.stderr)
        sys.exit(1)

    print(f"Resetting '{alias}'  (UID {uid})  target={target} ...")
    try:
        PyOCDWrapper.reset_target(uid, target, packs=proj.get("packs") or None)
        print(f"[ok] Reset complete for '{alias}'.")
    except Exception as e:
        print(f"[error] Reset failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_detect_target(cfg: ConfigManager, alias: str, project_name: str | None):
    """Auto-detect the MCU connected to a probe identified by alias."""
    proj = _get_project(cfg, project_name)
    uid, _ = _resolve_alias(proj, alias)

    if uid.upper() not in _connected_uid_set():
        print(f"[error] Probe '{alias}' (UID {uid}) is not connected.", file=sys.stderr)
        sys.exit(1)

    print(f"Detecting target for '{alias}' (UID {uid}) ...")
    detected = PyOCDWrapper.detect_target(uid)
    if detected:
        print(f"[ok] Detected target: {detected}")
    else:
        print("[warn] Could not auto-detect target.")


def cmd_list_targets():
    """Print all pyocd-supported target names."""
    targets = PyOCDWrapper.get_targets()
    if targets:
        for t in targets:
            print(f"  {t}")
    else:
        print("No targets found (is pyocd installed?).")
