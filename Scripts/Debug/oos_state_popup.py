#!/usr/bin/env python3
"""Integrated Oracle state capture UI with richer metadata and larger fonts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import messagebox, ttk
except ModuleNotFoundError:
    system_py = "/usr/bin/python3"
    if sys.executable != system_py and Path(system_py).exists():
        os.execv(system_py, [system_py, *sys.argv])
    raise


ROOT = Path(__file__).resolve().parents[1]
MESEN = [sys.executable, str(ROOT / "scripts" / "mesen2_client.py")]
SET_TRUSTED = [sys.executable, str(ROOT / "scripts" / "set_trusted_state_seed.py")]
SESSION_FILE = ROOT / ".context" / "scratchpad" / "oos_state_popup_session.json"
MACROS_FILE = ROOT / "Docs" / "Debugging" / "Testing" / "oos_ui_macros.json"
TASKS = ["maku", "d4", "d6", "d6inside", "d6cart", "menu"]


def run(cmd: list[str], *, expect_json: bool = False) -> Any:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"Command failed: {' '.join(cmd)}")
    return json.loads(proc.stdout) if expect_json else proc.stdout


def parse_profiles(raw: str) -> list[str]:
    return [m.group(1) for line in raw.splitlines() if (m := re.match(r"\s+([a-zA-Z0-9_.-]+):", line))]


def parse_fly_locations(raw: str) -> list[str]:
    return [m.group(1) for line in raw.splitlines() if (m := re.match(r"\s+([a-zA-Z0-9_]+):\s", line))]


def load_macros_config(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise RuntimeError(f"Macro config not found: {path}")
    data = json.loads(path.read_text())
    macros = data.get("macros", [])
    if not isinstance(macros, list) or not macros:
        raise RuntimeError(f"Macro config has no macros: {path}")
    required = {"id", "label", "steps"}
    for macro in macros:
        if not required.issubset(set(macro.keys())):
            raise RuntimeError(f"Macro missing required keys {required}: {macro}")
        steps = macro.get("steps")
        if not isinstance(steps, list) or not steps:
            raise RuntimeError(f"Macro '{macro.get('id')}' must define a non-empty steps list.")
        for step in steps:
            if not isinstance(step, dict) or "action" not in step:
                raise RuntimeError(f"Macro '{macro.get('id')}' has invalid step: {step}")
            action = step.get("action")
            if action == "apply_profile" and "profile" not in step:
                raise RuntimeError(f"Macro '{macro.get('id')}' apply_profile step requires 'profile'.")
            if action == "setflag" and ("flag" not in step or "value" not in step):
                raise RuntimeError(f"Macro '{macro.get('id')}' setflag step requires 'flag' and 'value'.")
            if action == "fly" and "location" not in step:
                raise RuntimeError(f"Macro '{macro.get('id')}' fly step requires 'location'.")
            if action == "frame" and "frames" not in step:
                raise RuntimeError(f"Macro '{macro.get('id')}' frame step requires 'frames'.")
    return macros


def load_session() -> dict[str, Any]:
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except Exception:
            pass
    return {"actions": [], "applied_profiles": []}


def save_session(state: dict[str, Any]) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(state, indent=2) + "\n")


def add_action(session: dict[str, Any], action: str, detail: str) -> None:
    session.setdefault("actions", [])
    session["actions"].append({"at": dt.datetime.now().isoformat(timespec="seconds"), "action": action, "detail": detail})
    session["actions"] = session["actions"][-40:]


class OracleStatePopupUI(tk.Tk):
    def __init__(self, instance: str, font_size: int, refresh_ms: int, theme: str, layout: str, macros_path: Path):
        super().__init__()
        self.instance = instance
        self.refresh_ms = refresh_ms
        self.theme = theme
        self.layout = layout
        self.macro_profiles = load_macros_config(macros_path)
        self.session = load_session()

        self.title(f"Oracle State Control - {instance}")
        self.geometry("1240x860")
        self.minsize(1100, 760)

        default_font = tkfont.nametofont("TkDefaultFont")
        text_font = tkfont.nametofont("TkTextFont")
        fixed_font = tkfont.nametofont("TkFixedFont")
        default_font.configure(size=font_size)
        text_font.configure(size=font_size)
        fixed_font.configure(size=max(font_size - 1, 11))
        self._apply_styles(font_size)

        self.metadata_var = tk.StringVar(value="Loading metadata...")
        self.status_var = tk.StringVar(value="Ready.")
        self.last_state_id_var = tk.StringVar(value="-")

        self.capture_label_var = tk.StringVar(value="manual seed")
        self.capture_tags_var = tk.StringVar(value="manual,popup")
        self.verify_now_var = tk.BooleanVar(value=True)
        self.verifier_var = tk.StringVar(value=os.getenv("USER", "scawful"))
        self.trusted_task_var = tk.StringVar(value="(none)")

        self.profile_var = tk.StringVar()
        self.crystal_var = tk.StringVar(value="0")
        self.gamestate_var = tk.StringVar(value="2")
        self.warp_var = tk.StringVar()

        self.profiles: list[str] = []
        self.locations: list[str] = []
        self._refresh_scheduled = False
        self.macro_buttons: list[ttk.Button] = []
        self.shortcut_descriptions: list[str] = []

        self._build_ui(font_size)
        self._wire_shortcuts()
        if hasattr(self, "shortcuts_var"):
            self.shortcuts_var.set(" | ".join(self.shortcut_descriptions[:6]))
        self._load_dynamic_options()
        self.refresh_metadata_once()
        self.start_auto_refresh()

    def _apply_styles(self, font_size: int) -> None:
        style = ttk.Style(self)
        if self.theme == "system":
            base_bg = self.cget("bg")
            panel_bg = base_bg
            fg = "#1f2937"
            muted = "#4b5563"
            accent = "#1d4ed8"
            border = "#cbd5e1"
            text_bg = "#ffffff"
        else:
            style.theme_use("clam")
            if self.theme == "light":
                base_bg = "#f4f6fb"
                panel_bg = "#ffffff"
                fg = "#1f2937"
                muted = "#4b5563"
                accent = "#1d4ed8"
                border = "#d1d5db"
                text_bg = "#ffffff"
            else:
                base_bg = "#111827"
                panel_bg = "#1f2937"
                fg = "#e5e7eb"
                muted = "#9ca3af"
                accent = "#60a5fa"
                border = "#374151"
                text_bg = "#0f172a"

        self.configure(bg=base_bg)
        style.configure(".", font=("Helvetica", font_size), foreground=fg)
        style.configure("TFrame", background=base_bg)
        style.configure("TLabel", background=base_bg, foreground=fg)
        style.configure("Muted.TLabel", background=base_bg, foreground=muted)
        style.configure("Header.TLabel", background=base_bg, foreground=accent, font=("Helvetica", font_size + 3, "bold"))
        style.configure("TLabelframe", background=base_bg, bordercolor=border, relief="solid")
        style.configure("TLabelframe.Label", background=base_bg, foreground=accent, font=("Helvetica", font_size + 1, "bold"))
        style.configure("TButton", padding=(10, 8), font=("Helvetica", font_size))
        style.configure("Accent.TButton", padding=(10, 8), font=("Helvetica", font_size, "bold"))
        style.configure("TEntry", fieldbackground=text_bg)
        style.configure("TCombobox", fieldbackground=text_bg)
        style.configure("TCheckbutton", background=base_bg, foreground=fg)
        style.configure("TSeparator", background=border)

    def _build_ui(self, font_size: int) -> None:
        top = ttk.Frame(self, padding=12)
        top.pack(fill="both", expand=True)

        ttk.Label(top, text="Oracle Testing Control Center", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            top,
            text="Metadata-aware capture, progression controls, and one-click setup macros.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 8))

        metadata_frame = ttk.LabelFrame(top, text="Live Context", padding=10)
        metadata_frame.pack(fill="x")
        ttk.Label(metadata_frame, textvariable=self.metadata_var, justify="left").pack(anchor="w", fill="x")

        middle = ttk.Frame(top)
        middle.pack(fill="both", expand=True, pady=(10, 0))

        left = ttk.Frame(middle)
        left.pack(side="left", fill="both", expand=True)
        right = ttk.Frame(middle)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))

        if self.layout == "compact":
            left.pack_configure(fill="both", expand=False)
            right.pack_configure(fill="both", expand=True)

        # Capture panel
        cap = ttk.LabelFrame(left, text="State Capture", padding=10)
        cap.pack(fill="x")
        ttk.Label(cap, text="Label").grid(row=0, column=0, sticky="w")
        ttk.Entry(cap, textvariable=self.capture_label_var, width=50).grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Label(cap, text="Tags (comma-separated)").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cap, textvariable=self.capture_tags_var, width=50).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Checkbutton(cap, text="Verify as canon now", variable=self.verify_now_var).grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(cap, textvariable=self.verifier_var, width=20).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Label(cap, text="Map as trusted task").grid(row=3, column=0, sticky="w", pady=(8, 0))
        trusted_combo = ttk.Combobox(cap, textvariable=self.trusted_task_var, state="readonly", width=18, values=["(none)"] + TASKS)
        trusted_combo.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Button(cap, text="Capture State", command=self.capture_state).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        cap.columnconfigure(1, weight=1)
        if self.layout == "compact":
            # Keep operator mode tight: collapse advanced capture defaults.
            self.capture_tags_var.set("manual,popup,operator")

        # Actions panel
        actions = ttk.LabelFrame(left, text="Quick Actions", padding=10)
        actions.pack(fill="x", pady=(10, 0))

        ttk.Label(actions, text="Profile").grid(row=0, column=0, sticky="w")
        self.profile_combo = ttk.Combobox(actions, textvariable=self.profile_var, state="readonly", width=26)
        self.profile_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Button(actions, text="Apply Profile", command=self.apply_profile).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(actions, text="Crystals").grid(row=1, column=0, sticky="w", pady=(8, 0))
        crystal_combo = ttk.Combobox(actions, textvariable=self.crystal_var, state="readonly", width=8, values=["0", "1", "3", "5", "7"])
        crystal_combo.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        ttk.Button(actions, text="Apply", command=self.apply_crystals).grid(row=1, column=2, padx=(8, 0), pady=(8, 0))

        ttk.Label(actions, text="GameState").grid(row=2, column=0, sticky="w")
        gamestate_combo = ttk.Combobox(actions, textvariable=self.gamestate_var, state="readonly", width=8, values=["0", "1", "2", "3"])
        gamestate_combo.grid(row=2, column=1, sticky="w", padx=(8, 0))
        ttk.Button(actions, text="Apply", command=self.apply_gamestate).grid(row=2, column=2, padx=(8, 0))

        ttk.Label(actions, text="Warp").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.warp_combo = ttk.Combobox(actions, textvariable=self.warp_var, state="readonly", width=26)
        self.warp_combo.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Button(actions, text="Fly", command=self.apply_warp).grid(row=3, column=2, padx=(8, 0), pady=(8, 0))

        ttk.Button(actions, text="Sync WRAMSAVE -> SRAM", command=self.sync_sram).grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Refresh Metadata", command=self.refresh_metadata_once).grid(row=5, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        actions.columnconfigure(1, weight=1)
        if self.layout == "compact":
            ttk.Separator(left).pack(fill="x", pady=(8, 0))
            ttk.Label(
                left,
                text="Operator mode: macros + shortcuts are primary controls.",
                style="Muted.TLabel",
            ).pack(anchor="w", pady=(8, 0))

        # Macro panel
        macro_frame = ttk.LabelFrame(right, text="Scenario Macros", padding=10)
        macro_frame.pack(fill="x")
        ttk.Label(
            macro_frame,
            text="Macros load from Docs/Debugging/Testing/oos_ui_macros.json",
            style="Muted.TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        for i, macro in enumerate(self.macro_profiles, start=1):
            label = str(macro.get("label", macro.get("id", f"macro_{i}")))
            shortcut = str(macro.get("shortcut", "")).strip()
            text = f"{label} ({shortcut})" if shortcut else label
            button_style = "Accent.TButton" if macro.get("primary", False) else "TButton"
            btn = ttk.Button(
                macro_frame,
                text=text,
                style=button_style,
                command=lambda m=macro: self.run_macro(m),
            )
            col_span = 3 if self.layout == "compact" else 1
            if self.layout == "compact":
                btn.grid(row=i, column=0, columnspan=col_span, sticky="ew", pady=(8, 0))
            else:
                row = ((i - 1) // 2) + 1
                col = (i - 1) % 2
                btn.grid(row=row, column=col, sticky="ew", pady=(8, 0), padx=(0 if col == 0 else 8, 0))
            self.macro_buttons.append(btn)
        macro_frame.columnconfigure(0, weight=1)
        macro_frame.columnconfigure(1, weight=1)

        # Log panel
        log_frame = ttk.LabelFrame(right, text="Session Action Log", padding=10)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.log_text = tk.Text(log_frame, height=28, wrap="word", font=("Menlo", max(font_size - 1, 11)))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")
        ttk.Button(log_frame, text="Clear Log", command=self.clear_log).pack(fill="x", pady=(8, 0))

        footer = ttk.Frame(top, padding=(0, 8, 0, 0))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status_var).pack(side="left")
        ttk.Label(footer, text="Last state ID:").pack(side="left", padx=(16, 4))
        ttk.Label(footer, textvariable=self.last_state_id_var).pack(side="left")
        self.shortcuts_var = tk.StringVar(value="")
        ttk.Label(footer, textvariable=self.shortcuts_var, style="Muted.TLabel").pack(side="right")

    def _load_dynamic_options(self) -> None:
        profiles_raw = run(MESEN + ["--instance", self.instance, "save-data", "profile-list"])
        self.profiles = parse_profiles(profiles_raw)
        self.profile_combo["values"] = self.profiles
        if self.profiles:
            self.profile_var.set(self.profiles[0])

        fly_raw = run(MESEN + ["--instance", self.instance, "fly", "--list"])
        self.locations = parse_fly_locations(fly_raw)
        self.warp_combo["values"] = self.locations
        if self.locations:
            self.warp_var.set(self.locations[0])

    def _add_log(self, action: str, detail: str) -> None:
        add_action(self.session, action, detail)
        save_session(self.session)
        self._render_log()

    def _render_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        for row in self.session.get("actions", []):
            self.log_text.insert("end", f"[{row['at']}] {row['action']}: {row['detail']}\n")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _register_shortcut(self, key: str, callback, description: str) -> None:
        def _wrapped(_event=None):
            focused = self.focus_get()
            if focused is not None:
                klass = focused.winfo_class()
                # Do not fire global shortcuts while typing in text inputs.
                if klass in {"Entry", "TEntry", "Text", "TCombobox", "Combobox"}:
                    return None
            callback()
            return "break"

        self.bind_all(key, _wrapped)
        self.shortcut_descriptions.append(f"{key} -> {description}")

    def _wire_shortcuts(self) -> None:
        self._register_shortcut("<Control-r>", self.refresh_metadata_once, "Refresh metadata")
        self._register_shortcut("<Control-s>", self.sync_sram, "Sync WRAMSAVE->SRAM")
        self._register_shortcut("<Control-Shift-C>", self.capture_state, "Capture state")
        self._register_shortcut("<Control-p>", self.apply_profile, "Apply selected profile")
        self._register_shortcut("<Control-w>", self.apply_warp, "Warp to selected location")
        self._register_shortcut("<Control-l>", self.clear_log, "Clear action log")

        # Macro shortcuts from JSON profile.
        for macro in self.macro_profiles:
            shortcut = macro.get("shortcut")
            if shortcut:
                self._register_shortcut(shortcut, lambda m=macro: self.run_macro(m), f"Macro: {macro.get('label')}")

    def _apply_profile_named(self, profile: str, *, sync: bool = True) -> None:
        if profile not in self.profiles:
            raise RuntimeError(f"Profile not found: {profile}")
        run(MESEN + ["--instance", self.instance, "save-data", "profile-apply", profile])
        if sync:
            run(MESEN + ["--instance", self.instance, "save-data", "sync-to-sram"])
        self._add_log("profile", profile)

    def _execute_macro_step(self, step: dict[str, Any], title: str) -> None:
        action = step.get("action")
        if action == "apply_profile":
            profile = str(step.get("profile", "")).strip()
            if not profile:
                raise RuntimeError(f"Macro '{title}' step missing profile: {step}")
            self._apply_profile_named(profile, sync=False)
            self._add_log("macro-step", f"{title}: apply_profile {profile}")
            return
        if action == "setflag":
            flag = str(step.get("flag", "")).strip()
            value = str(step.get("value", "")).strip()
            if not flag or value == "":
                raise RuntimeError(f"Macro '{title}' step missing flag/value: {step}")
            run(MESEN + ["--instance", self.instance, "setflag", flag, value])
            self._add_log("macro-step", f"{title}: setflag {flag}={value}")
            return
        if action == "sync_sram":
            run(MESEN + ["--instance", self.instance, "save-data", "sync-to-sram"])
            self._add_log("macro-step", f"{title}: sync WRAMSAVE->SRAM")
            return
        if action == "fly":
            location = str(step.get("location", "")).strip()
            if not location:
                raise RuntimeError(f"Macro '{title}' step missing location: {step}")
            run(MESEN + ["--instance", self.instance, "fly", location])
            self._add_log("macro-step", f"{title}: fly {location}")
            return
        if action == "frame":
            frames = int(step.get("frames", 0))
            if frames <= 0:
                raise RuntimeError(f"Macro '{title}' frame step requires frames>0: {step}")
            run(MESEN + ["--instance", self.instance, "frame", str(frames)])
            self._add_log("macro-step", f"{title}: frame {frames}")
            return
        raise RuntimeError(f"Unknown macro action '{action}' in {title}")

    def run_macro(self, macro: dict[str, Any]) -> None:
        def _do() -> None:
            title = str(macro.get("label", macro.get("id", "macro")))
            steps = macro.get("steps", [])
            if not isinstance(steps, list) or not steps:
                raise RuntimeError(f"Macro '{title}' has no steps.")
            for step in steps:
                self._execute_macro_step(step, title)
            self._add_log("macro", str(macro.get("id", title)))
            self._set_status(f"{title} complete.")

        self._safe_action(_do)

    def _safe_action(self, fn) -> None:
        try:
            fn()
        except Exception as exc:
            messagebox.showerror("Oracle State UI", str(exc))
            self._set_status(f"Error: {exc}")

    def refresh_metadata_once(self) -> None:
        def _do() -> None:
            diag = run(MESEN + ["--instance", self.instance, "diagnostics", "--json"], expect_json=True)
            story = run(MESEN + ["--instance", self.instance, "story", "--json"], expect_json=True)
            oracle = diag.get("oracle_state", {})
            run_state = diag.get("run_state", {})
            last_load = (run_state.get("lastLoad") or {}).get("path") or "-"
            summary = (
                f"Mode: {oracle.get('mode_name')} | Submode: {oracle.get('submode')} | Indoors: {oracle.get('indoors')}\n"
                f"Area: {oracle.get('area_name')} | Room: {oracle.get('room_name')} | Dungeon room: {oracle.get('dungeon_room')}\n"
                f"Link: x={oracle.get('link_x')} y={oracle.get('link_y')} dir={oracle.get('link_dir_name')} state={oracle.get('link_state')} form={oracle.get('link_form_name')}\n"
                f"Vitals: HP {oracle.get('health')}/{oracle.get('max_health')} | Magic {oracle.get('magic')} | Rupees {oracle.get('rupees')}\n"
                f"Story: GameState={story.get('game_state')} OOSPROG={story.get('oosprog')} OOSPROG2={story.get('oosprog2')} Cutscene={story.get('in_cutscene')}\n"
                f"Progression: Crystals={story.get('crystals')} Pendants={story.get('pendants')} MakuQuest={story.get('maku_tree_quest')}\n"
                f"Runtime: frame={run_state.get('frame')} paused={run_state.get('paused')} lastLoadedState={last_load}"
            )
            self.metadata_var.set(summary)
            self._render_log()
            self._set_status("Metadata refreshed.")

        self._safe_action(_do)

    def start_auto_refresh(self) -> None:
        if self._refresh_scheduled:
            return
        self._refresh_scheduled = True

        def _tick() -> None:
            self.refresh_metadata_once()
            self.after(self.refresh_ms, _tick)

        self.after(self.refresh_ms, _tick)

    def apply_profile(self) -> None:
        def _do() -> None:
            profile = self.profile_var.get().strip()
            if not profile:
                raise RuntimeError("Choose a profile first.")
            self._apply_profile_named(profile)
            self._set_status(f"Applied profile: {profile}")

        self._safe_action(_do)

    def apply_crystals(self) -> None:
        def _do() -> None:
            chosen = self.crystal_var.get().strip()
            bitfield = {"0": "0x00", "1": "0x01", "3": "0x15", "5": "0x1F", "7": "0x7F"}.get(chosen)
            if bitfield is None:
                raise RuntimeError("Choose crystal count 0/1/3/5/7.")
            run(MESEN + ["--instance", self.instance, "setflag", "crystals", bitfield])
            run(MESEN + ["--instance", self.instance, "save-data", "sync-to-sram"])
            self._add_log("crystals", f"{chosen} ({bitfield})")
            self._set_status(f"Set crystals to {chosen}.")

        self._safe_action(_do)

    def apply_gamestate(self) -> None:
        def _do() -> None:
            value = self.gamestate_var.get().strip()
            run(MESEN + ["--instance", self.instance, "setflag", "gamestate", value])
            run(MESEN + ["--instance", self.instance, "save-data", "sync-to-sram"])
            self._add_log("gamestate", value)
            self._set_status(f"Set GameState to {value}.")

        self._safe_action(_do)

    def apply_warp(self) -> None:
        def _do() -> None:
            loc = self.warp_var.get().strip()
            if not loc:
                raise RuntimeError("Choose a warp destination first.")
            run(MESEN + ["--instance", self.instance, "fly", loc])
            self._add_log("warp", loc)
            self._set_status(f"Warped to {loc}.")

        self._safe_action(_do)

    def sync_sram(self) -> None:
        def _do() -> None:
            run(MESEN + ["--instance", self.instance, "save-data", "sync-to-sram"])
            self._add_log("sync", "WRAMSAVE->SRAM")
            self._set_status("Synced WRAMSAVE -> SRAM.")

        self._safe_action(_do)

    def capture_state(self) -> None:
        def _do() -> None:
            label = self.capture_label_var.get().strip()
            if not label:
                raise RuntimeError("Label is required.")
            tags = [t.strip() for t in self.capture_tags_var.get().split(",") if t.strip()]
            cmd = MESEN + ["--instance", self.instance, "lib-save", label, "--captured-by", "human", "--json"]
            for t in tags:
                cmd += ["-t", t]
            out = run(cmd, expect_json=True)
            state_id = out.get("id") or out.get("state_id") or (out.get("entry") or {}).get("id")
            if not state_id:
                raise RuntimeError(f"Could not parse state id from output: {out}")

            if self.verify_now_var.get():
                run(MESEN + ["--instance", self.instance, "lib-verify", state_id, "--by", self.verifier_var.get().strip() or "scawful"])

            task = self.trusted_task_var.get()
            if task and task != "(none)":
                run(SET_TRUSTED + [task, state_id])
                self._add_log("trusted-seed", f"{task}={state_id}")

            self.last_state_id_var.set(state_id)
            self._add_log("capture", f"{state_id} tags={','.join(tags) if tags else '-'}")
            self._set_status(f"Captured state: {state_id}")
            messagebox.showinfo("Oracle State UI", f"Captured state:\n{state_id}")

        self._safe_action(_do)

    def clear_log(self) -> None:
        self.session["actions"] = []
        save_session(self.session)
        self._render_log()
        self._set_status("Action log cleared.")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", default=os.getenv("MESEN2_INSTANCE", "oos-codex-live-20260406"))
    parser.add_argument("--font-size", type=int, default=16, help="Base UI font size")
    parser.add_argument("--refresh-ms", type=int, default=2000, help="Metadata refresh interval in milliseconds")
    parser.add_argument("--theme", choices=["dark", "light", "system"], default="dark", help="UI theme")
    parser.add_argument("--layout", choices=["full", "compact"], default="full", help="UI layout mode")
    parser.add_argument("--macros-file", default=str(MACROS_FILE), help="JSON file describing macro buttons and steps")
    args = parser.parse_args()

    run(MESEN + ["--instance", args.instance, "health"])
    app = OracleStatePopupUI(
        args.instance,
        max(args.font_size, 11),
        max(args.refresh_ms, 500),
        args.theme,
        args.layout,
        Path(args.macros_file),
    )
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
