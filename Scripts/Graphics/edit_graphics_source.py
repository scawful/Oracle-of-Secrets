#!/usr/bin/env python3
"""Review and publish one canonical V2 graphics resource without writing a ROM.

`plan --replacement FILE --plan RECEIPT` records exact source and portable-pack
inputs. `apply --plan RECEIPT` recompiles that proposal and publishes it with
compare-and-swap guards and rollback. Palette colors remain native ROM data.
Publication is rollback protected, not crash atomic across the complete file set.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tempfile

sys.dont_write_bytecode = True

import compile_graphics_pack as pack
import compile_runtime_graphics as runtime

LOCK_NAME = ".yaze-message-source-sync.lock"
SOURCE_CATALOG = "Overworld/graphics_catalog.json"
SOURCE_POLICY = "Overworld/graphics_runtime_policy.json"
SOURCE_TABLES = "Overworld/graphics_runtime_tables.asm"


class EditError(ValueError):
    """The reviewed source transaction cannot safely proceed."""


def absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def plain(path: Path, *, missing: bool = False, directory: bool = False) -> Path:
    """Reject symbolic links in every component and multiply linked files."""
    path = absolute(path)
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            if missing and part == path:
                return path
            raise EditError(f"Missing publication path: {part}")
        if stat.S_ISLNK(info.st_mode):
            raise EditError(f"Symbolic links are not source publication paths: {part}")
        if part != path or directory:
            if not stat.S_ISDIR(info.st_mode):
                raise EditError(f"Publication parent is not a directory: {part}")
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise EditError(f"Source publication requires a regular file with one hard link: {part}")
    return path


def relative_asset(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name:
        raise EditError("Resource path must be a nonempty portable path")
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts or "\\" in name:
        raise EditError(f"Resource path escapes its catalog: {name}")
    path = absolute(root / name)
    if not path.is_relative_to(root):
        raise EditError(f"Resource path escapes its catalog: {name}")
    return plain(path)


def snapshot(path: Path) -> tuple[dict, bytes]:
    path = plain(path)
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    identity = lambda value: (value.st_dev, value.st_ino, value.st_mtime_ns,
                              value.st_size, value.st_mode, value.st_nlink)
    if identity(before) != identity(after) or len(data) != after.st_size:
        raise EditError(f"Source changed during read: {path}")
    return dict(path=str(path), sha256=pack.sha256(data), byte_count=len(data),
                device=after.st_dev, inode=after.st_ino, mtime_ns=after.st_mtime_ns), data


def check_snapshot(expected: dict) -> None:
    actual, _ = snapshot(Path(expected["path"]))
    if actual != expected:
        raise EditError(f"Source changed since plan: {expected['path']}")


def semantic(catalog: dict) -> dict:
    result = copy.deepcopy(catalog)
    for resource in result["resources"].values():
        resource.pop("path", None)
    return result


def collect(source_root: Path, portable_catalog: Path, resource_id: str) -> tuple[dict, dict, dict]:
    """Load both catalogs and pin every compiler, resource and receipt input."""
    root = plain(source_root, directory=True)
    portable_catalog = plain(portable_catalog)
    if portable_catalog.name != "catalog.json":
        raise EditError("Portable pack publication requires its catalog.json entry point")
    source_directory = plain(root / "Overworld", directory=True)
    if (portable_catalog.parent.is_relative_to(source_directory) or
            source_directory.is_relative_to(portable_catalog.parent)):
        raise EditError("Canonical source and portable pack publication folders must not overlap")
    canonical_path = plain(root / SOURCE_CATALOG)
    # The shared reader accepts symlinks that stay inside a portable pack.
    # Writable sources require stricter paths before any binary is opened.
    for catalog_path in (canonical_path, portable_catalog):
        document = pack.read_json(catalog_path)
        for value in pack.object_value(document.get("resources"), "resources").values():
            relative_asset(catalog_path.parent, value["path"])
    canonical, assets = pack.load(canonical_path)
    portable, portable_assets = pack.load(portable_catalog)
    if semantic(canonical) != semantic(portable) or assets != portable_assets:
        raise EditError("Portable graphics pack differs from canonical source")
    if resource_id not in canonical["resources"]:
        raise EditError(f"Unknown graphics resource: {resource_id}")
    resource = canonical["resources"][resource_id]
    if resource_id != "snes4bpp:" + resource["sha256"].lower():
        raise EditError("Writable resources must use their exact snes4bpp:SHA256 content ID")
    paths = {canonical_path, root / SOURCE_POLICY, root / SOURCE_TABLES, portable_catalog}
    for catalog_path, catalog in ((canonical_path, canonical), (portable_catalog, portable)):
        for value in catalog["resources"].values():
            paths.add(relative_asset(catalog_path.parent, value["path"]))
    paths.update(root / "Overworld" / name for name in runtime.LEGACY_ALIASES)
    # Compile with the reviewed implementation, while aliases resolve in the
    # selected source repository rather than the script's own checkout.
    paths.update(Path(__file__).parent / name for name in
                 ("edit_graphics_source.py", "compile_graphics_pack.py", "compile_runtime_graphics.py"))
    receipt_path = portable_catalog.parent / "receipt.json"
    if receipt_path.exists():
        receipt = pack.read_json(plain(receipt_path))
        paths.add(receipt_path)
        for name, expected in pack.object_value(receipt.get("files"), "pack receipt files").items():
            target = relative_asset(portable_catalog.parent, name)
            recorded, _ = snapshot(target)
            if (recorded["sha256"] != expected["sha256"] or
                    recorded["byte_count"] != expected["byte_count"]):
                raise EditError(f"Portable graphics receipt differs from saved file: {target}")
            paths.add(target)
        if (receipt.get("catalog_sha256") != pack.sha256(portable_catalog.read_bytes()) or
                receipt.get("source_sha256") != pack.sha256(canonical_path.read_bytes())):
            raise EditError("Portable graphics receipt differs from canonical catalog")
        policy_digest = receipt.get("runtime_policy_source_sha256")
        if policy_digest is not None and policy_digest != pack.sha256((root / SOURCE_POLICY).read_bytes()):
            raise EditError("Portable graphics receipt differs from canonical runtime policy")
    snapshots, contents, identities = [], {}, {}
    for path in sorted(paths):
        record, data = snapshot(path)
        identity = (record["device"], record["inode"])
        if identity in identities and identities[identity] != record["path"]:
            raise EditError(f"Source inputs alias one another: {path}")
        identities[identity] = record["path"]
        snapshots.append(record)
        contents[record["path"]] = data
    # Check bytes loaded by the catalog parser against the pinned readback.
    for catalog_path, catalog, loaded in ((canonical_path, canonical, assets),
                                          (portable_catalog, portable, portable_assets)):
        for key, value in catalog["resources"].items():
            if contents[str(absolute(catalog_path.parent / value["path"]))] != loaded[key]:
                raise EditError("Graphics resource changed during catalog validation")
    table_text, _ = runtime.compile_tables(canonical_path, root / SOURCE_POLICY,
                                           root / SOURCE_TABLES, legacy_root=root)
    if table_text.encode() != contents[str(root / SOURCE_TABLES)]:
        raise EditError("Canonical runtime tables are stale; review and regenerate them before editing")
    contracts = {}
    profiles, parents, transfers = [], set(), []
    for profile_id, profile in canonical["profiles"].items():
        selected = [t for t in profile["transfers"] if t["resource_id"] == resource_id]
        if not selected:
            continue
        profiles.append(profile_id)
        bound = sorted(p for b in canonical["bindings"] if b["profile_id"] == profile_id
                       for p in b["parent_maps"])
        parents.update(bound)
        transfers.extend(dict(t, profile_id=profile_id, parent_maps=bound) for t in selected)
        if "authoring_contract" in profile:
            contracts[profile_id] = profile["authoring_contract"]
    if not profiles:
        raise EditError("Resource has no editable profile transfers")
    info = dict(schema_version=1, operation="inspect", result="ok", source_root=str(root),
                portable_catalog=str(portable_catalog), before_resource_id=resource_id,
                resource_format=resource["format"], resource_byte_count=resource["byte_count"],
                resource_sha256=resource["sha256"],
                source_resource_path=str(absolute(canonical_path.parent / resource["path"])),
                portable_resource_path=str(absolute(portable_catalog.parent / portable["resources"][resource_id]["path"])),
                affected_profiles=sorted(profiles), affected_parent_maps=sorted(parents),
                transfers=transfers, authoring_contracts=contracts, inputs=snapshots)
    return info, canonical, contents


def rewrite_references(value, before: str, after: str):
    if isinstance(value, dict):
        return {key: after if key == "resource_id" and item == before else
                rewrite_references(item, before, after) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_references(item, before, after) for item in value]
    return value


def staged_outputs(info: dict, catalog: dict, contents: dict, replacement: bytes) -> tuple[dict, dict]:
    root, portable = Path(info["source_root"]), Path(info["portable_catalog"])
    if len(replacement) != info["resource_byte_count"]:
        raise EditError("Replacement must preserve the resource byte count and slice layout")
    before, digest = info["before_resource_id"], pack.sha256(replacement)
    after = "snes4bpp:" + digest
    updated = rewrite_references(copy.deepcopy(catalog), before, after)
    resource = updated["resources"].pop(before)
    if after != before and after in updated["resources"]:
        existing = updated["resources"][after]
        if existing["sha256"] != digest or existing["byte_count"] != len(replacement):
            raise EditError("Replacement content ID conflicts with an existing resource")
        resource = existing
    else:
        # Retaining alias-backed legacy binaries is essential: old assembly
        # labels keep their bytes, and new art receives a separate payload.
        if after != before:
            resource["path"] = f"gfx/source-{digest}.4bpp.bin"
        resource["sha256"] = digest
    updated["resources"][after] = resource
    policy = rewrite_references(json.loads(contents[str(root / SOURCE_POLICY)]), before, after)
    outputs = {}
    with tempfile.TemporaryDirectory(prefix="yaze-graphics-source-") as directory:
        stage = Path(directory).resolve() / "Overworld"
        stage.mkdir()
        for key, value in updated["resources"].items():
            destination = stage / value["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = replacement if key == after else contents[str(root / "Overworld" / value["path"])]
            destination.write_bytes(data)
        stage_catalog, stage_policy = stage / "graphics_catalog.json", stage / "graphics_runtime_policy.json"
        stage_catalog.write_bytes(pack.json_bytes(updated))
        stage_policy.write_bytes(pack.json_bytes(policy))
        table_text, runtime_report = runtime.compile_tables(
            stage_catalog, stage_policy, stage / "graphics_runtime_tables.asm", legacy_root=root)
        portable_stage = Path(directory).resolve() / "portable"
        pack.compile_pack(stage_catalog, portable_stage, runtime_policy=stage_policy)
        outputs[root / SOURCE_CATALOG] = stage_catalog.read_bytes()
        outputs[root / SOURCE_POLICY] = stage_policy.read_bytes()
        outputs[root / SOURCE_TABLES] = table_text.encode()
        outputs[root / "Overworld" / resource["path"]] = replacement
        for file in sorted(portable_stage.rglob("*")):
            if file.is_file():
                outputs[portable.parent / file.relative_to(portable_stage)] = file.read_bytes()
    result = dict(after_resource_id=after,
                  after_source_resource_path=str(root / "Overworld" / resource["path"]),
                  after_portable_resource_path=str(portable.parent / f"assets/{digest}.4bpp.bin"),
                  runtime_report=runtime_report)
    return outputs, result


def make_plan(source_root: Path, portable: Path, resource_id: str, replacement: Path) -> dict:
    info, catalog, contents = collect(source_root, portable, resource_id)
    replacement_record, data = snapshot(replacement)
    if replacement_record["path"] in contents:
        raise EditError("Replacement must be a distinct reviewed input file")
    outputs, result = staged_outputs(info, catalog, contents, data)
    changes, targets = [], []
    input_paths = {record["path"] for record in info["inputs"]}
    info["inputs"].append(replacement_record)
    for target, after in sorted(outputs.items()):
        target = plain(target, missing=True)
        before = None
        if target.exists():
            record, before = snapshot(target)
            if str(target) not in input_paths:
                info["inputs"].append(record)
                input_paths.add(str(target))
        targets.append(dict(path=str(target), before_sha256=pack.sha256(before) if before is not None else None))
        if before != after:
            changes.append(dict(path=str(target), before_sha256=pack.sha256(before) if before is not None else None,
                                after_sha256=pack.sha256(after), byte_count=len(after)))
    info.update(result, operation="plan", replacement_path=replacement_record["path"],
                replacement_sha256=replacement_record["sha256"], changed_files=changes,
                publication_targets=targets)
    info["inputs"].sort(key=lambda value: value["path"])
    for record in info["inputs"]:
        check_snapshot(record)
    return info


@contextlib.contextmanager
def publication_locks(targets: list[dict]):
    handles = []
    try:
        directories = sorted({str(plain(Path(t["path"]).parent, directory=True)) for t in targets})
        for name in directories:
            path = plain(Path(name) / LOCK_NAME, missing=True)
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            handles.append(fd)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise EditError(f"Invalid source publication lock: {path}")
            # Fail promptly; the UI can retry after the other publisher finishes.
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise EditError(f"Source publication is busy: {path}") from exc
        yield
    finally:
        for fd in reversed(handles):
            os.close(fd)


def replace_file(path: Path, data: bytes) -> None:
    """Same-directory fsynced temporary plus atomic target replacement."""
    plain(path, missing=True)
    descriptor, name = tempfile.mkstemp(prefix=".graphics-source-", dir=path.parent)
    temporary = Path(name)
    try:
        if path.exists():
            os.fchmod(descriptor, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def target_unchanged(target: dict) -> None:
    path = plain(Path(target["path"]), missing=True)
    actual = pack.sha256(path.read_bytes()) if path.exists() else None
    if actual != target["before_sha256"]:
        raise EditError(f"Publication target changed since plan: {path}")


def apply_plan(plan: dict, source_root: Path, portable: Path, resource_id: str | None = None,
               *, plan_guard: dict | None = None) -> dict:
    if (plan.get("schema_version") != 1 or plan.get("operation") != "plan" or
            plan.get("source_root") != str(absolute(source_root)) or
            plan.get("portable_catalog") != str(absolute(portable)) or
            resource_id is not None and resource_id != plan.get("before_resource_id")):
        raise EditError("Graphics plan does not match the selected source, pack and resource")
    # Receipt fields are untrusted. Recompute the bounded target set before
    # acquiring locks; a forged receipt cannot create locks outside the pack.
    current = make_plan(source_root, portable, plan["before_resource_id"], Path(plan["replacement_path"]))
    if current != plan:
        raise EditError("Recompiled graphics proposal differs from the reviewed plan")
    if plan_guard is not None:
        check_snapshot(plan_guard)
    with publication_locks(current["publication_targets"]):
        for record in plan["inputs"]:
            check_snapshot(record)
        for target in plan["publication_targets"]:
            target_unchanged(target)
        current = make_plan(source_root, portable, plan["before_resource_id"], Path(plan["replacement_path"]))
        if current != plan:
            raise EditError("Recompiled graphics proposal differs from the reviewed plan")
        info, catalog, contents = collect(source_root, portable, plan["before_resource_id"])
        outputs, _ = staged_outputs(info, catalog, contents, Path(plan["replacement_path"]).read_bytes())
        originals = {Path(t["path"]): (Path(t["path"]).read_bytes() if t["before_sha256"] is not None else None)
                     for t in plan["changed_files"]}
        original_records = {Path(record["path"]): record for record in plan["inputs"]}
        changed_paths = set(originals)
        input_guards = [r for r in plan["inputs"] if Path(r["path"]) not in changed_paths]
        if plan_guard is not None:
            input_guards.append(plan_guard)
        published = []
        try:
            for change in plan["changed_files"]:
                for record in input_guards:
                    check_snapshot(record)
                target_unchanged(change)
                target = Path(change["path"])
                if target in original_records:
                    check_snapshot(original_records[target])
                data = outputs[target]
                if pack.sha256(data) != change["after_sha256"]:
                    raise EditError(f"Staged output differs from plan: {target}")
                replace_file(target, data)
                published.append(target)
            for target, data in outputs.items():
                if plain(target).read_bytes() != data:
                    raise EditError(f"Published graphics readback differs: {target}")
            # Final compiler and catalog checks execute before rollback copies
            # are released. Build Project's stale-table guard consumes this ASM.
            root = Path(plan["source_root"])
            text, _ = runtime.compile_tables(root / SOURCE_CATALOG, root / SOURCE_POLICY,
                                             root / SOURCE_TABLES, legacy_root=root)
            if (root / SOURCE_TABLES).read_bytes() != text.encode():
                raise EditError("Published runtime tables differ from canonical source")
            collect(root, Path(plan["portable_catalog"]), plan["after_resource_id"])
            for record in input_guards:
                check_snapshot(record)
        except BaseException as failure:
            conflicts = []
            for target in reversed(published):
                if not target.exists() or plain(target).read_bytes() != outputs[target]:
                    conflicts.append(str(target))
                    continue
                if originals[target] is None:
                    target.unlink()
                else:
                    replace_file(target, originals[target])
            if conflicts:
                raise EditError("Rollback refused externally changed files: " + ", ".join(conflicts)) from failure
            raise
    result = copy.deepcopy(plan)
    result.update(operation="apply", result="published")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("inspect", "plan", "apply"))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--portable-catalog", type=Path, required=True)
    parser.add_argument("--resource-id")
    parser.add_argument("--replacement", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--expected-plan-sha256",
                        help="admit the exact held review-plan bytes before apply")
    args = parser.parse_args(argv)
    try:
        if args.operation == "apply":
            if args.plan is None:
                raise EditError("apply requires --plan")
            plan_guard, plan_bytes = snapshot(args.plan)
            if (args.expected_plan_sha256 is not None and
                    args.expected_plan_sha256.lower() != plan_guard["sha256"]):
                raise EditError("Graphics plan SHA256 differs from the held review")
            plan = pack.object_value(json.loads(plan_bytes, object_pairs_hook=pack._unique_object),
                                     "graphics edit plan")
            result = apply_plan(plan, args.source_root, args.portable_catalog, args.resource_id,
                                plan_guard=plan_guard)
        elif args.resource_id is None:
            raise EditError("inspect and plan require --resource-id")
        elif args.operation == "inspect":
            result, _, _ = collect(args.source_root, args.portable_catalog, args.resource_id)
        else:
            if args.replacement is None or args.plan is None:
                raise EditError("plan requires --replacement and --plan")
            result = make_plan(args.source_root, args.portable_catalog, args.resource_id, args.replacement)
            target = plain(args.plan, missing=True)
            with target.open("xb") as stream:
                stream.write(pack.json_bytes(result))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (EditError, pack.PackError, OSError, KeyError, TypeError, ValueError) as error:
        print(json.dumps(dict(schema_version=1, operation=args.operation, result="error", error=str(error))))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
