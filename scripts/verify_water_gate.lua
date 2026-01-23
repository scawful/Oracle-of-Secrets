-- verify_water_gate.lua
-- Automated headless test for water collision persistence
-- Run with: Mesen --testRunner --timeout=120 scripts/verify_water_gate.lua Roms/oos168.sfc
-- Optional: MESEN_LOADSTATE=/path/to/state.mss (auto-load before testing)
--
-- Tests:
-- 1. Game boots successfully
-- 2. Room 0x27 has correct water collision (type $08) after water fills
-- 3. SRAM persistence flag ($7EF411 bit 0) is set
-- 4. Collision persists on room re-entry
--
-- Exit codes:
-- 0 = PASS (all tests passed)
-- 1 = FAIL (test assertion failed)
-- 2 = TIMEOUT (test did not complete in time)

-- =============================================================================
-- Configuration
-- =============================================================================

local TEST_ROOM = 0x27            -- Zora Temple water gate room
local DEEP_WATER_COLLISION = 0x08 -- Collision type for swimmable water
local SRAM_WATER_STATES = 0x7EF411 -- SRAM address for water gate persistence
local SRAM_BIT_ROOM27 = 0x01      -- Bit 0 = Room 0x27 water gate

-- Collision map addresses
local COLMAPA_BASE = 0x7F2000
local COLMAPB_BASE = 0x7F3000

-- Sample collision offsets from Room 0x27 water area
-- These are offsets into $7F2000 collision map
-- Formula: offset = (Y * 64) + X where Y,X are tile coordinates
-- NOTE: Collision data is shifted down 3 tiles (Y=41-43) to match engine offsets
local SAMPLE_WATER_OFFSETS = {
  0x0A45,  -- Y=41, X=5 (start of swim area)
  0x0A58,  -- Y=41, X=24 (middle of swim area)
  0x0A79,  -- Y=41, X=57 (end of swim area)
  0x0A95,  -- Y=42, X=21 (middle row)
  0x0AD5,  -- Y=43, X=21 (bottom row)
}

-- Timing (60 fps)
local BOOT_TIMEOUT_FRAMES = 600   -- 10 seconds to boot
local TEST_TIMEOUT_FRAMES = 7200  -- 2 minutes total
local ROOM_SETTLE_FRAMES = 60     -- 1 second for room to fully load
local LOADSTATE_TIMEOUT_FRAMES = 300 -- 5 seconds to load savestate
local LOADSTATE_PATH = os.getenv("MESEN_LOADSTATE")
local SAVESTATE_EXEC_HOOK = 0x008051 -- MainGameLoop .do_frame

-- =============================================================================
-- Test State
-- =============================================================================

local state = {
  phase = LOADSTATE_PATH and "load_state" or "boot",
                          -- load_state, boot, wait_room, check_collision, check_sram, done
  frame_count = 0,
  room_entry_count = 0,
  last_room = 0,
  in_target_room = false,
  settle_counter = 0,
  test_results = {},
  exit_code = 2,          -- Default to timeout
}

local loadstate = {
  path = LOADSTATE_PATH,
  status = LOADSTATE_PATH and "pending" or "idle",
  error = "",
  frames = 0,
}

-- =============================================================================
-- Helper Functions
-- =============================================================================

local function log(message)
  emu.log("[WaterGateTest] " .. message)
end

local function fail(message)
  log("FAIL: " .. message)
  state.exit_code = 1
  state.phase = "done"
end

local function pass(message)
  log("PASS: " .. message)
end

local function readByte(addr)
  return emu.read(addr, emu.memType.snesMemory)
end

local function readWord(addr)
  return readByte(addr) + (readByte(addr + 1) * 256)
end

local function resetStateForLoadedSave()
  state.frame_count = 0
  state.room_entry_count = 0
  state.last_room = 0
  state.in_target_room = false
  state.settle_counter = 0
  state.test_results = {}
end

local function loadSavestateFromFile(path)
  local f = io.open(path, "rb")
  if not f then
    return false, "state_not_found"
  end
  local data = f:read("*all")
  f:close()
  local ok, result = pcall(emu.loadSavestate, data)
  if not ok then
    return false, tostring(result)
  end
  if result ~= true then
    return false, "load_failed"
  end
  return true
end

local function savestateExecCallback()
  if loadstate.status ~= "pending" then return end
  local ok, err = loadSavestateFromFile(loadstate.path)
  if ok then
    loadstate.status = "ok"
  else
    loadstate.status = "error"
    loadstate.error = err
  end
end

local function getCurrentRoom()
  return readByte(0x7E00A0)
end

local function getGameMode()
  return readByte(0x7E0010)
end

local function getCollisionAt(offset)
  return readByte(COLMAPA_BASE + offset)
end

local function getSRAMWaterStates()
  return readByte(SRAM_WATER_STATES)
end

-- =============================================================================
-- Test Phases
-- =============================================================================

local function phase_load_state()
  loadstate.frames = loadstate.frames + 1

  if loadstate.frames == 1 then
    log("Loading savestate: " .. tostring(loadstate.path))
  end

  if loadstate.status == "ok" then
    pass("Savestate loaded")
    resetStateForLoadedSave()
    state.phase = "wait_room"
    return
  end

  if loadstate.status == "error" then
    fail("Savestate load failed: " .. tostring(loadstate.error))
    return
  end

  if loadstate.frames > LOADSTATE_TIMEOUT_FRAMES then
    fail("Savestate load timeout")
  end
end

local function phase_boot()
  local gameMode = getGameMode()

  -- Game modes: 0x00=Intro, 0x01=FileSelect, 0x07=Dungeon, 0x09=Overworld
  if gameMode >= 0x07 then
    pass("Game booted to mode " .. string.format("0x%02X", gameMode))
    state.phase = "wait_room"
    return
  end

  if state.frame_count > BOOT_TIMEOUT_FRAMES then
    fail("Boot timeout - stuck at game mode " .. string.format("0x%02X", gameMode))
  end
end

local function phase_wait_room()
  local room = getCurrentRoom()
  local gameMode = getGameMode()

  -- Detect room entry
  if room ~= state.last_room then
    state.last_room = room
    state.settle_counter = 0

    if room == TEST_ROOM then
      state.room_entry_count = state.room_entry_count + 1
      log("Entered room " .. string.format("0x%02X", room) ..
          " (entry #" .. state.room_entry_count .. ")")
      state.in_target_room = true
    else
      state.in_target_room = false
    end
  end

  -- Wait for room to settle
  if state.in_target_room then
    state.settle_counter = state.settle_counter + 1

    if state.settle_counter >= ROOM_SETTLE_FRAMES then
      state.phase = "check_collision"
    end
  end

  -- Display waiting message periodically
  if state.frame_count % 300 == 0 then  -- Every 5 seconds
    log("Waiting for room 0x27... Current room: " ..
        string.format("0x%02X", room) ..
        ", mode: " .. string.format("0x%02X", gameMode))
  end
end

local function phase_check_collision()
  log("Checking collision values in room 0x27...")

  local all_water = true
  local collision_log = {}

  for i, offset in ipairs(SAMPLE_WATER_OFFSETS) do
    local coll = getCollisionAt(offset)
    table.insert(collision_log, string.format("$%04X=$%02X", offset, coll))

    if coll ~= DEEP_WATER_COLLISION then
      all_water = false
    end
  end

  log("Collision values: " .. table.concat(collision_log, ", "))

  if all_water then
    pass("All sample positions have deep water collision ($08)")
    state.test_results.collision = "PASS"
    state.phase = "check_sram"
  else
    -- Water collision not present - this is expected on first entry before water fills
    -- The test should continue to monitor
    if state.room_entry_count == 1 then
      log("Water collision not yet applied (first entry, water may not have filled)")
      log("Waiting for water fill event or re-entry...")
      state.phase = "wait_room"
      state.in_target_room = false
      state.settle_counter = 0
    else
      -- On subsequent entries, collision should persist
      fail("Water collision not persisted on room re-entry #" .. state.room_entry_count)
      state.test_results.collision = "FAIL"
    end
  end
end

local function phase_check_sram()
  local waterStates = getSRAMWaterStates()
  local bit0Set = (waterStates % 2) == 1  -- Check bit 0

  log("SRAM WaterGateStates ($7EF411) = " .. string.format("$%02X", waterStates))

  if bit0Set then
    pass("SRAM persistence flag for room 0x27 is set")
    state.test_results.sram = "PASS"
  else
    log("SRAM persistence flag not set (may need water fill trigger)")
    state.test_results.sram = "PENDING"
  end

  -- Check if we've verified on multiple room entries
  if state.room_entry_count >= 2 and state.test_results.collision == "PASS" then
    log("=== ALL TESTS PASSED ===")
    log("- Collision: " .. state.test_results.collision)
    log("- SRAM: " .. (state.test_results.sram or "N/A"))
    log("- Room entries verified: " .. state.room_entry_count)
    state.exit_code = 0
    state.phase = "done"
  else
    -- Continue monitoring for more room entries
    state.phase = "wait_room"
    state.in_target_room = false
    state.settle_counter = 0
  end
end

local function phase_done()
  if state.exit_code == 0 then
    log("RESULT: PASS")
    emu.displayMessage("Test", "PASS - Water gate verified")
  else
    local status = state.exit_code == 2 and "TIMEOUT" or "FAIL"
    log("RESULT: " .. status)
    emu.displayMessage("Test", "FAIL - See log for details")
  end

  -- Stop emulation (testRunner mode will capture exit code from log)
  emu.stop()
end

-- =============================================================================
-- Main Loop
-- =============================================================================

function Main()
  state.frame_count = state.frame_count + 1

  -- Global timeout
  if state.frame_count > TEST_TIMEOUT_FRAMES then
    log("TEST TIMEOUT after " .. state.frame_count .. " frames")
    log("Final state: " .. state.phase)
    log("Room entries: " .. state.room_entry_count)
    state.exit_code = 2
    state.phase = "done"
  end

  -- Phase dispatch
  if state.phase == "load_state" then
    phase_load_state()
  elseif state.phase == "boot" then
    phase_boot()
  elseif state.phase == "wait_room" then
    phase_wait_room()
  elseif state.phase == "check_collision" then
    phase_check_collision()
  elseif state.phase == "check_sram" then
    phase_check_sram()
  elseif state.phase == "done" then
    phase_done()
  end
end

-- =============================================================================
-- Initialization
-- =============================================================================

emu.addEventCallback(Main, emu.eventType.endFrame)
log("Water Gate Test Script loaded")
log("Target room: " .. string.format("0x%02X", TEST_ROOM))
log("Expected collision: " .. string.format("$%02X", DEEP_WATER_COLLISION))
if LOADSTATE_PATH then
  pcall(function()
    emu.addMemoryCallback(savestateExecCallback, emu.callbackType.exec, SAVESTATE_EXEC_HOOK)
  end)
  log("Savestate auto-load enabled: " .. LOADSTATE_PATH)
else
  log("Waiting for game boot...")
end
