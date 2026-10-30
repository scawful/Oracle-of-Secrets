# Room scenarios: fast reset and fresh replay

Use one existing JSON case to exercise pre-entry, controller entry, readiness,
interaction, and return. The strict runner attaches to one owned Mesen socket.
It does not build, launch an emulator, choose a checkpoint, or create a worktree.

The two checks answer different questions:

1. **Fast reset:** reload the same hash-bound pre-entry state before every run.
   This isolates repeatability within one owned process.
2. **Fresh replay:** start a fresh isolated process/profile with the pinned ROM
   and SRM, then replay the same case. This checks process/session initialization
   separately. Loading a pre-entry state still restores captured machine state;
   it does not prove an unaided route from cold boot or Save & Quit.

Both retain their own receipts. Neither establishes human gameplay acceptance.

## Pin the baseline before entering the room

1. Record the exact patched runtime ROM path and SHA-256, source/build receipt,
   symbols, feature profile, emulator binary/version, and intended room behavior.
   An editable base ROM is not the compiled Oracle runtime.
2. Record the initial SRM path/hash, relevant settings/input files, and any
   profile/checkpoint setup. Stage only owned copies into an isolated profile.
   Record a deliberately absent SRM as
   such; do not silently inherit a default-profile save.
3. Apply the intended checkpoint/profile **before** normal room entry. Verify
   starting room/area, full room ID, collision plane, position/facing, equipment,
   health/resources, and room/progression flags. Setup assistance is a fixture.
4. Capture a compatible pre-entry savestate, retain its SHA-256, and record how
   it was produced. The case must enter through controller input and wait for
   exact ready conditions. Writing room coordinates after loading is not entry.
5. Keep the baseline immutable. If the ROM, SRM, state, profile, checkpoint,
   feature set, or route changes, qualify that new tuple before reuse.

The legacy `Data/debug/save_state_library.json` contains historical D6 and Zora
seeds. `inside_d6` is a draft with an older ROM MD5; other entries carry February
metadata. Their names, `canon` labels, or old load reports do not bind them to a
current candidate. No compatible current tuple is supplied by this example.

## Use the existing owned headless session workflow

Read AFS `scratchpad/board_rules.md` and the canonical
`mesen2-oos-debugging` skill before an episode. Claim the existing native lane
through `Scripts/Agents/heavy_lock.py`; bind its token to a live supervising
worker and retain actual worker/emulator PIDs and start times. Never create or
remove lock files manually. Hold the lease until owned native exit is confirmed.

For a new session, use the existing launcher with explicit private paths:

```sh
export MESEN2_OOS_ROOT=/Users/scawful/src/hobby/mesen2-oos
Scripts/Mesen2/mesen2_launch_instance.sh \
  --instance "$SCENARIO_INSTANCE" --owner "$SCENARIO_OWNER" \
  --source room-scenario --rom "$SCENARIO_ROM" \
  --app "$SCENARIO_APP" \
  --home "$SCENARIO_PROFILE" --socket "$SCENARIO_SOCKET" \
  --headless --no-save-settings --no-copy-settings \
  --no-state-set --no-seed-project-states
```

Set these variables to the reviewed episode's values and stage its owned profile
configuration first. Do not run the template unchanged. On macOS apply the
current `taskpolicy -b -p <owned-emulator-pid>`
rule. Confirm the actual process, socket, ROM and registry identity after launch;
a launcher exit or stale socket alone does not establish ownership.

Use the existing registry record created by the launcher, not a fabricated JSON
record or a status file. The registry helper uses `MESEN2_REGISTRY_DIR` when set;
otherwise inspect its current `instances` directory and select the exact claimed
instance. Pass that record's path and matching owner to the runner. Do not use
`--socket-force`, `--no-register`, default-profile permission, or newest-socket
discovery to bypass a missing binding. Never target `oos-rc-play` or another owner.

## Run the strict case

Inspect the selected checkout's `test_runner.py --help` first. It must expose
`--room-scenario`; an older installed runner is not interchangeable.

```sh
python3 -B Scripts/Validate/test_runner.py "$SCENARIO_CASE" \
  --room-scenario \
  --rom "$SCENARIO_ROM" \
  --expected-rom-sha256 "$SCENARIO_ROM_SHA256" \
  --mesen-socket "$SCENARIO_SOCKET" \
  --session-record "$SCENARIO_SESSION_RECORD" \
  --session-owner "$SCENARIO_OWNER" \
  --expected-state-sha256 "$SCENARIO_STATE_SHA256" \
  --repeat 3 --output-format json > "$SCENARIO_RECEIPT"
```

Select exactly one case. Use its explicit `saveState.path`; relative state paths
resolve against the case file. Hashes must come from the actual files, not this
guide. The case, ROM, state and session binding must pass before controller input.
Fast repetition reloads the whole baseline and rechecks its preconditions on each
run. It does not continue from the prior run's final room or remaining resources.
Setup initializes the debugger before pausing, then verifies that the loaded
baseline remains paused at one frame while preconditions and fixtures are checked.
Actions resume the owned instance. Finite inputs record frame observations after
acknowledgement and release input before the next action; input-poll counts and
polling overshoot do not establish exact cycle timing.
The first failure stops the run; retain it before triage. Do not skip missing
state, preconditions, checks or failed repetitions to obtain a passing receipt.

For fresh replay, end the owned process through the existing session workflow,
confirm its exit, and release its lease. Acquire a new episode, use a fresh private
profile with the same declared SRM/setup, and launch the same pinned ROM. Bind the
new socket/registry record and run the same case with `--repeat 1`. Keep its receipt
separate from fast repetitions. If a true boot-to-room replay is required, run the
reviewed controller route from the declared save/checkpoint before state capture;
do not describe a savestate reload as that proof.

## Case format and example

`Tests/examples/room_scenario.json` is intentionally **UNBOUND**. Its state path
does not exist, its controller durations need calibration, and no hashes or
compatible starting save are claimed. It illustrates room `$98` → `$97`, an
inventory open/close interaction, and return. It does not qualify the cart gate,
lever, enemies, item progression, or a natural route. Replace the interaction with
the intended mechanic and its observable postconditions for a real scenario.

The strict format reuses the existing runner:

- `saveState` contains only `path`. No ID/slot lookup, fallback, `allowMissing`,
  cache-reload request, or implicit state pack is accepted.
- Preconditions use the existing list or address-map conditions. Use `size: 2`
  for full 16-bit room IDs, positions and other words; byte reads are the default.
- Steps are `press`, `wait`, `assert`, `wait_addr`/`wait-address`,
  `wait_state`/`wait-state`, `screenshot`, or `comment`. Check descriptions must
  be nonempty and unique. Require an exact entry and return, not “room changed.”
- There are no `exec`, raw `command`, memory-write steps, or skip paths. An
  optional `fixtures` list may declare only `write`/`write16` entries with address,
  value and description. The runner applies them after initial preconditions,
  reads them back, and discloses them. The example has none.
- Repeat count is 1–100. A case timeout is finite, positive and at most 300 seconds.
  Do not make invincibility, no-damage mode or enemy deactivation a default fixture.

Cleanup rechecks the binding, releases player-0 input, and confirms that the owned
session is paused. It leaves the debugger attached and does not depend on the
unregistered `STOP_DEBUGGER` command. End that owned process and release its native
lease through the existing episode workflow; the runner does neither automatically.

Use screenshots for visible evidence alongside named state checks. A successful
memory assertion does not prove comfortable movement, readable attacks, correct
animation, or player acceptance. Preserve fixture assistance in every claim.

## Known limits and evidence

- Old entrance-table tools can read the vanilla table while Oracle uses the
  ZScream bank `$0F` table. Pin the actual entrance source and typed room links.
- Legacy validators or byte-only room checks may mishandle high room IDs. Keep
  `$100`–`$127` as full words, and do not truncate or substitute a low-byte room.
- A spatial/validator pass does not qualify custom actors, hooks, all collision
  states, water restoration, movement, or a compatible savestate.
- Save-state repeatability and fresh-process replay are separate from ordinary
  save/fresh-load persistence and human gameplay feedback.
- Retain exact inputs, registry/session binding, declared fixtures, named-check
  results, failure/timeout, and cleanup confirmation in the existing AFS handoff.
  Reuse this checkout and one case specification; do not build or create a
  worktree for each case. No state or ROM asset belongs in the example commit.
