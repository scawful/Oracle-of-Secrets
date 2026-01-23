"""CLI entrypoint for the Oracle Mesen2 debug client."""

import argparse
import json
import sys

from .client import OracleDebugClient
from .constants import ITEMS, STORY_FLAGS, WARP_LOCATIONS, WATCH_PROFILES
from .paths import MANIFEST_PATH


def main():
    parser = argparse.ArgumentParser(description="Oracle of Secrets Debug Client")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # State command
    state_parser = subparsers.add_parser("state", help="Show game state")
    state_parser.add_argument("--json", "-j", action="store_true")

    # Story command
    story_parser = subparsers.add_parser("story", help="Show story progress")
    story_parser.add_argument("--json", "-j", action="store_true")

    # Watch command
    watch_parser = subparsers.add_parser("watch", help="Watch addresses")
    watch_parser.add_argument("--profile", "-p", default="overworld")
    watch_parser.add_argument("--json", "-j", action="store_true")

    # Sprites command
    sprites_parser = subparsers.add_parser("sprites", help="Debug sprites")
    sprites_parser.add_argument("--slot", "-s", type=int, default=0)
    sprites_parser.add_argument("--all", "-a", action="store_true")
    sprites_parser.add_argument("--json", "-j", action="store_true")

    # Profiles command
    profiles_parser = subparsers.add_parser("profiles", help="List watch profiles")
    profiles_parser.add_argument("--json", "-j", action="store_true")

    # Assistant command
    subparsers.add_parser("assistant", help="Live debug assistant")

    # === NEW COMMANDS ===

    # Items command
    items_parser = subparsers.add_parser("items", help="List/get items")
    items_parser.add_argument("item", nargs="?", help="Item name to get")
    items_parser.add_argument("--json", "-j", action="store_true")

    # Give command (set item)
    give_parser = subparsers.add_parser("give", help="Give item to Link")
    give_parser.add_argument("item", help="Item name")
    give_parser.add_argument("value", type=int, help="Value to set")

    # Flags command
    flags_parser = subparsers.add_parser("flags", help="List/get story flags")
    flags_parser.add_argument("flag", nargs="?", help="Flag name to get")
    flags_parser.add_argument("--json", "-j", action="store_true")

    # Set flag command
    setflag_parser = subparsers.add_parser("setflag", help="Set a story flag")
    setflag_parser.add_argument("flag", help="Flag name")
    setflag_parser.add_argument("value", help="Value (number or true/false)")

    # Warp command
    warp_parser = subparsers.add_parser("warp", help="Warp Link to location")
    warp_parser.add_argument("location", nargs="?", help="Location name or 'list'")
    warp_parser.add_argument("--area", "-a", type=lambda x: int(x, 0))
    warp_parser.add_argument("--x", type=int)
    warp_parser.add_argument("--y", type=int)
    warp_parser.add_argument("--kind", "-k", default="ow", help="ow=overworld, uw=underworld")

    # Press command (input injection)
    press_parser = subparsers.add_parser("press", help="Press buttons")
    press_parser.add_argument("buttons", help="Comma-separated buttons (a,b,up,down,etc)")
    press_parser.add_argument("--frames", "-f", type=int, default=5)

    # Position command
    pos_parser = subparsers.add_parser("pos", help="Set Link position")
    pos_parser.add_argument("x", type=int)
    pos_parser.add_argument("y", type=int)

    # Control commands
    subparsers.add_parser("pause", help="Pause emulation")
    subparsers.add_parser("resume", help="Resume emulation")
    subparsers.add_parser("reset", help="Reset game")

    # Frame advance
    frame_parser = subparsers.add_parser("frame", help="Advance frames")
    frame_parser.add_argument("count", type=int, nargs="?", default=1)

    # Save state commands
    save_parser = subparsers.add_parser("save", help="Save state")
    save_parser.add_argument("slot", type=int, nargs="?", help="Slot number (1-10)")
    save_parser.add_argument("--path", "-p", help="Custom save path")

    load_parser = subparsers.add_parser("load", help="Load state")
    load_parser.add_argument("slot", type=int, nargs="?", help="Slot number (1-10)")
    load_parser.add_argument("--path", "-p", help="Custom load path")

    # Library commands
    lib_parser = subparsers.add_parser("library", help="List library entries")
    lib_parser.add_argument("--tag", "-t", help="Filter by tag")
    lib_parser.add_argument("--json", "-j", action="store_true")

    lib_load_parser = subparsers.add_parser("lib-load", help="Load state from library by ID")
    lib_load_parser.add_argument("state_id", help="State ID from library")

    lib_info_parser = subparsers.add_parser("lib-info", help="Show library entry details")
    lib_info_parser.add_argument("state_id", help="State ID")
    lib_info_parser.add_argument("--json", "-j", action="store_true")

    capture_parser = subparsers.add_parser("capture", help="Capture current state metadata")
    capture_parser.add_argument("--json", "-j", action="store_true")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Handle commands that don't require connection first
    if args.command == "profiles":
        if args.json:
            profiles = {name: p["description"] for name, p in WATCH_PROFILES.items()}
            print(json.dumps(profiles, indent=2))
        else:
            print("=== Available Watch Profiles ===")
            for name, p in WATCH_PROFILES.items():
                print(f"  {name}: {p['description']}")
        return

    if args.command == "items" and not args.item:
        # List available items
        print("=== Available Items ===")
        for name, (addr, desc, vals) in ITEMS.items():
            print(f"  {name}: {desc}")
        return

    if args.command == "flags" and not args.flag:
        # List available flags
        print("=== Available Flags ===")
        for name, (addr, desc, mask) in STORY_FLAGS.items():
            bit_info = f" (bit 0x{mask:02X})" if isinstance(mask, int) else ""
            print(f"  {name}: {desc}{bit_info}")
        return

    if args.command == "warp" and args.location == "list":
        print("=== Warp Locations ===")
        for name, (area, x, y, desc) in WARP_LOCATIONS.items():
            print(f"  {name}: {desc} (area=0x{area:02X}, x={x}, y={y})")
        return

    client = OracleDebugClient()

    if not client.is_connected():
        print("ERROR: Cannot connect to Mesen2. Is it running with socket enabled?")
        print("Looking for socket at: /tmp/mesen2-*.sock")
        sys.exit(1)

    if args.command == "state":
        state = client.get_oracle_state()
        if args.json:
            print(json.dumps(state, indent=2))
        else:
            print("=== Oracle Game State ===")
            print(f"Mode: {state['mode_name']} (0x{state['mode']:02X})")
            print(f"Area: 0x{state['area']:02X}")
            print(f"Room: 0x{state['room']:02X}")
            print(f"Indoors: {bool(state['indoors'])}")
            print(f"Link: ({state['link_x']}, {state['link_y']}, Z={state['link_z']})")
            print(f"Direction: {state['link_dir_name']}")
            print(f"Scroll: ({state['scroll_x']}, {state['scroll_y']})")

            # Check for issues
            warnings = client.check_known_issues(state)
            if warnings:
                print("\n=== Warnings ===")
                for w in warnings:
                    print(w)

    elif args.command == "story":
        story = client.get_story_state()
        if args.json:
            print(json.dumps(story, indent=2))
        else:
            print("=== Story Progress ===")
            print(f"GameState: {story['game_state']}")
            print(f"OOSPROG: 0x{story['oosprog']:02X}")
            print(f"OOSPROG2: 0x{story['oosprog2']:02X}")
            print(f"SideQuest: 0x{story['side_quest']:02X}")
            print(f"Crystals: 0x{story['crystals']:02X}")
            print(f"Pendants: 0x{story['pendants']:02X}")
            print(f"Maku Tree Met: {bool(story['maku_tree_quest'])}")
            print(f"In Cutscene: {bool(story['in_cutscene'])}")

    elif args.command == "watch":
        if not client.set_watch_profile(args.profile):
            print(f"Unknown profile: {args.profile}")
            print(f"Available: {', '.join(WATCH_PROFILES.keys())}")
            sys.exit(1)

        values = client.read_watch_values()
        profile_info = WATCH_PROFILES[args.profile]

        if args.json:
            print(json.dumps({"profile": args.profile, "values": values}, indent=2))
        else:
            print(f"=== Watch Profile: {args.profile} ===")
            print(f"({profile_info['description']})")
            for name, val in values.items():
                print(f"  {name}: {val}")

    elif args.command == "sprites":
        if args.all:
            sprites = client.get_all_sprites()
            if args.json:
                print(json.dumps(sprites, indent=2))
            else:
                print(f"=== Active Sprites ({len(sprites)}) ===")
                for spr in sprites:
                    print(
                        f"  Slot {spr['slot']}: Type=0x{spr['type']:02X} "
                        f"State=0x{spr['state']:02X} "
                        f"Pos=({spr['x']},{spr['y']}) "
                        f"Action={spr['action']} HP={spr['health']}"
                    )
        else:
            slot = client.get_sprite_slot(args.slot)
            if args.json:
                print(json.dumps(slot, indent=2))
            else:
                print(f"=== Sprite Slot {args.slot} ===")
                print(f"  Type: 0x{slot['type']:02X}")
                print(f"  State: 0x{slot['state']:02X}")
                print(f"  Position: ({slot['x']}, {slot['y']})")
                print(f"  Action: {slot['action']}")
                print(f"  Health: {slot['health']}")
                print(f"  TimerA: {slot['timer_a']}")
                print(f"  TimerB: {slot['timer_b']}")
                print(f"  TimerD: {slot['timer_d']}")
                print(f"  Parent: {slot['parent']}")

    elif args.command == "assistant":
        print("=== Debug Assistant Mode ===")
        print("Monitoring area changes and known issues...")
        print("Press Ctrl+C to exit")
        print()

        import time

        last_area = None
        while True:
            try:
                state = client.get_oracle_state()
                current_area = state["area"]

                if current_area != last_area:
                    msg = client.on_area_change(current_area)
                    print(msg)
                    print(f"  Mode: {state['mode_name']}")
                    print(f"  Profile: {client._watch_profile}")

                    values = client.read_watch_values()
                    for name, val in values.items():
                        print(f"  {name}: {val}")

                    warnings = client.check_known_issues(state)
                    for w in warnings:
                        print(w)
                    print()

                last_area = current_area
                time.sleep(0.1)  # 10Hz polling

            except KeyboardInterrupt:
                print("\nExiting.")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(1)

    # === NEW COMMAND HANDLERS ===

    elif args.command == "items":
        if args.item:
            try:
                val, desc = client.get_item(args.item)
                if args.json:
                    print(json.dumps({"item": args.item, "value": val, "description": desc}))
                else:
                    print(f"{args.item}: {desc} (value={val})")
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
        else:
            # Show all items with values
            items = client.get_all_items()
            if args.json:
                print(json.dumps(items, indent=2))
            else:
                print("=== Current Items ===")
                for name, data in items.items():
                    if data["value"] != 0:
                        print(f"  {name}: {data['description']} (value={data['value']})")

    elif args.command == "give":
        try:
            if client.set_item(args.item, args.value):
                print(f"Set {args.item} = {args.value}")
            else:
                print(f"Failed to set {args.item}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "flags":
        if args.flag:
            try:
                val, is_set = client.get_flag(args.flag)
                if args.json:
                    print(json.dumps({"flag": args.flag, "value": val, "is_set": is_set}))
                else:
                    print(f"{args.flag}: {'SET' if is_set else 'NOT SET'} (raw=0x{val:02X})")
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
        else:
            # Show all flags with values
            flags = client.get_all_flags()
            if args.json:
                print(json.dumps(flags, indent=2))
            else:
                print("=== Current Flags ===")
                for name, data in flags.items():
                    status = "SET" if data["is_set"] else "---"
                    print(f"  {name}: {status} (0x{data['value']:02X})")

    elif args.command == "setflag":
        try:
            # Parse value - could be number or true/false
            if args.value.lower() in ("true", "1", "yes", "on"):
                value = True
            elif args.value.lower() in ("false", "0", "no", "off"):
                value = False
            else:
                value = int(args.value, 0)

            if client.set_flag(args.flag, value):
                print(f"Set {args.flag} = {value}")
            else:
                print(f"Failed to set {args.flag}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "warp":
        try:
            if args.location:
                if client.warp_to(location=args.location, kind=args.kind):
                    loc = WARP_LOCATIONS[args.location]
                    print(f"Warped to {args.location} ({loc[3]})")
                else:
                    print("Warp failed")
            elif args.area is not None and args.x is not None and args.y is not None:
                if client.warp_to(area=args.area, x=args.x, y=args.y, kind=args.kind):
                    print(f"Warped to area=0x{args.area:02X}, x={args.x}, y={args.y} (kind={args.kind})")
                else:
                    print("Warp failed")
            else:
                print("Usage: warp <location> OR warp --area 0xXX --x N --y N [--kind ow|uw]")
                print("Use 'warp list' to see available locations")
        except (ValueError, KeyError) as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "press":
        if client.press_button(args.buttons, args.frames):
            print(f"Pressed: {args.buttons}")
        else:
            print("Button press failed")

    elif args.command == "pos":
        if client.set_position(args.x, args.y):
            print(f"Set position to ({args.x}, {args.y})")
        else:
            print("Position set failed")

    elif args.command == "pause":
        if client.pause():
            print("Paused")
        else:
            print("Pause failed")

    elif args.command == "resume":
        if client.resume():
            print("Resumed")
        else:
            print("Resume failed")

    elif args.command == "reset":
        if client.reset():
            print("Reset")
        else:
            print("Reset failed")

    elif args.command == "frame":
        if client.run_frames(args.count):
            print(f"Advanced {args.count} frame(s)")
        else:
            print("Frame advance failed")

    elif args.command == "save":
        if args.path:
            if client.save_state(path=args.path):
                print(f"Saved to {args.path}")
            else:
                print("Save failed")
        elif args.slot:
            if client.save_state(slot=args.slot):
                print(f"Saved to slot {args.slot}")
            else:
                print("Save failed")
        else:
            print("Usage: save <slot> OR save --path <file>")

    elif args.command == "load":
        if args.path:
            if client.load_state(path=args.path):
                print(f"Loaded from {args.path}")
            else:
                print("Load failed")
        elif args.slot:
            if client.load_state(slot=args.slot):
                print(f"Loaded from slot {args.slot}")
            else:
                print("Load failed")
        else:
            print("Usage: load <slot> OR load --path <file>")

    # === STATE LIBRARY COMMANDS ===

    elif args.command == "library":
        entries = client.list_library_entries(tag=args.tag)
        if args.json:
            print(json.dumps(entries, indent=2))
        else:
            if not entries:
                print("No entries in library" + (f" with tag '{args.tag}'" if args.tag else ""))
                print(f"Manifest path: {MANIFEST_PATH}")
            else:
                print(f"=== State Library ({len(entries)} entries) ===")
                for entry in entries:
                    tags = ", ".join(entry.get("tags", []))
                    desc = entry.get("description", "No description")
                    print(f"  {entry['id']}: {desc}")
                    if tags:
                        print(f"    Tags: {tags}")

    elif args.command == "lib-load":
        try:
            if client.load_library_state(args.state_id):
                entry = client.find_library_entry(args.state_id)
                desc = entry.get("description", args.state_id) if entry else args.state_id
                print(f"Loaded: {desc}")
            else:
                print("Load failed")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "lib-info":
        entry = client.find_library_entry(args.state_id)
        if not entry:
            print(f"State '{args.state_id}' not found in library")
            sys.exit(1)

        if args.json:
            print(json.dumps(entry, indent=2))
        else:
            print(f"=== {entry['id']} ===")
            print(f"Description: {entry.get('description', 'N/A')}")
            print(f"Path: {entry.get('path', 'N/A')}")
            print(f"ROM Base: {entry.get('rom_base', 'N/A')}")
            print(f"Tags: {', '.join(entry.get('tags', []))}")
            if "gameState" in entry:
                gs = entry["gameState"]
                print(
                    f"Game State: mode={gs.get('mode', '?')}, submode={gs.get('submode', '?')}, indoors={gs.get('indoors', '?')}"
                )
            if "meta" in entry:
                print("Meta:")
                for k, v in entry["meta"].items():
                    print(f"  {k}: {v}")

    elif args.command == "capture":
        metadata = client.capture_state_metadata()
        if args.json:
            print(json.dumps(metadata, indent=2))
        else:
            print("=== Current State Metadata ===")
            print(f"Location: {metadata['location']}")
            print(f"Summary: {metadata['summary']}")
            print(f"Area: 0x{metadata['area']:02X}")
            print(f"Room: 0x{metadata['room']:02X}")
            print(f"Position: ({metadata['link_x']}, {metadata['link_y']})")
            print(f"Indoors: {metadata['indoors']}")
            print(f"GameState: {metadata['game_state']}")
            print(f"OOSPROG: 0x{metadata['oosprog']:02X}")
            print(f"OOSPROG2: 0x{metadata['oosprog2']:02X}")
            print(f"Crystals: 0x{metadata['crystals']:02X}")
            print(f"Pendants: 0x{metadata['pendants']:02X}")


if __name__ == "__main__":
    main()
