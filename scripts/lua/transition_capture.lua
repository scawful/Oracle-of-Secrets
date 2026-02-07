--[[
  Transition Capture Script for Mesen2 OOS

  Monitors key addresses during room transitions to help debug
  the black screen bug. Auto-captures state when anomalies detected.

  Usage: Load this script in Mesen2 via Debug > Scripting Window

  Key addresses monitored:
  - GameMode ($7E0010)
  - Submodule ($7E0011)
  - INIDISPQ ($7E0013)
  - FADETIME ($7EC007)
  - P register at hook entry points
]]

-- Configuration
local CONFIG = {
  -- How many frames to wait in a suspect state before capturing
  blackScreenThreshold = 90,  -- 1.5 seconds at 60fps

  -- Whether to auto-save state on anomaly
  autoSaveState = true,

  -- Log level: 0=errors only, 1=warnings, 2=info, 3=debug
  logLevel = 2,

  -- Output directory for captures
  outputDir = "debug_captures/",
}

-- Key RAM addresses
local RAM = {
  GAMEMODE = 0x7E0010,
  SUBMODULE = 0x7E0011,
  SUBSUBMODULE = 0x7E00B0,
  INIDISPQ = 0x7E0013,
  FRAME = 0x7E001A,
  FADETIME = 0x7EC007,
  FADETIME_HI = 0x7EC008,
  MOSAICLEVEL = 0x7EC011,
  LINK_X = 0x7E0022,
  LINK_Y = 0x7E0020,
  AREA_ID = 0x7E040A,
  ROOM_ID = 0x7E00A0,
}

-- Hook addresses to monitor for P register
local HOOKS = {
  { addr = 0x0289BF, name = "CheckForFollowerIntraroomTransition", expected_m = 16, expected_x = 8 },
  { addr = 0x028A5B, name = "CheckForFollowerInterroomTransition", expected_m = 8, expected_x = 8 },
  { addr = 0x2CC081, name = "CheckForFollowerIntraroomTransition", expected_m = 16, expected_x = 8 },
}

-- State tracking
local state = {
  blackScreenFrames = 0,
  lastCapture = 0,
  transitionStartFrame = 0,
  inTransition = false,
  lastGameMode = 0,
  lastSubmodule = 0,
  captureCount = 0,
  pMismatches = {},
  memWrites = {},
}

-- Utility functions
local function log(level, msg)
  if level <= CONFIG.logLevel then
    local prefix = ({"[ERROR]", "[WARN]", "[INFO]", "[DEBUG]"})[level + 1] or "[???]"
    emu.log(prefix .. " " .. msg)
  end
end

local function readByte(addr)
  return emu.read(addr, emu.memType.snesMemory)
end

local function readWord(addr)
  local lo = emu.read(addr, emu.memType.snesMemory)
  local hi = emu.read(addr + 1, emu.memType.snesMemory)
  return lo + (hi * 256)
end

local function formatHex(val, digits)
  digits = digits or 2
  return string.format("$%0" .. digits .. "X", val)
end

local function getCPUState()
  local cpu = emu.getState()
  if cpu and cpu.cpu then
    return cpu.cpu
  end
  return nil
end

-- Check if screen is blanked (potential black screen bug)
local function isScreenBlanked()
  local inidispq = readByte(RAM.INIDISPQ)
  return (inidispq & 0x80) ~= 0  -- Bit 7 = force blank (queued)
end

-- Check if we're in a transition state
local function isInTransition()
  local mode = readByte(RAM.GAMEMODE)
  local submod = readByte(RAM.SUBMODULE)

  -- Module 07 = Underworld, various submodules for transitions
  if mode == 0x07 then
    return submod ~= 0x00
  end

  -- Module 09 = Overworld, transition submodules
  if mode == 0x09 then
    return submod ~= 0x00
  end

  return false
end

-- Capture current state for debugging
local function captureState(reason)
  local frameCount = emu.getState().ppu.frameCount or 0

  -- Don't capture too frequently
  if frameCount - state.lastCapture < 60 then
    return
  end
  state.lastCapture = frameCount
  state.captureCount = state.captureCount + 1

  local capture = {
    reason = reason,
    frame = frameCount,
    timestamp = os.date("%Y%m%d_%H%M%S"),
    ram = {
      gameMode = readByte(RAM.GAMEMODE),
      submodule = readByte(RAM.SUBMODULE),
      subsubmodule = readByte(RAM.SUBSUBMODULE),
      frameCounter = readByte(RAM.FRAME),
      inidispq = readByte(RAM.INIDISPQ),
      fadeTime = readWord(RAM.FADETIME),
      mosaicLevel = readByte(RAM.MOSAICLEVEL),
      linkX = readWord(RAM.LINK_X),
      linkY = readWord(RAM.LINK_Y),
      areaId = readByte(RAM.AREA_ID),
      roomId = readWord(RAM.ROOM_ID),
    },
    pMismatches = state.pMismatches,
  }

  -- Log capture
  log(1, string.format("=== STATE CAPTURE: %s ===", reason))
  log(1, string.format("  GameMode: %s, Submodule: %s",
    formatHex(capture.ram.gameMode), formatHex(capture.ram.submodule)))
  log(1, string.format("  Frame: %s, INIDISPQ: %s (blank=%s)",
    formatHex(capture.ram.frameCounter), formatHex(capture.ram.inidispq), tostring(isScreenBlanked())))
  log(1, string.format("  FADETIME: %s, MosaicLevel: %s",
    formatHex(capture.ram.fadeTime, 4), formatHex(capture.ram.mosaicLevel)))
  log(1, string.format("  Link: X=%s, Y=%s",
    formatHex(capture.ram.linkX, 4), formatHex(capture.ram.linkY, 4)))
  log(1, string.format("  Area: %s, Room: %s",
    formatHex(capture.ram.areaId), formatHex(capture.ram.roomId, 4)))

  -- Log P mismatches if any
  if #state.pMismatches > 0 then
    log(1, "  P Register Mismatches:")
    for i, m in ipairs(state.pMismatches) do
      log(1, string.format("    %s: %s expected %d-bit, got %d-bit",
        formatHex(m.pc, 6), m.flag, m.expected, m.actual))
    end
  end

  -- Auto-save state if enabled
  if CONFIG.autoSaveState then
    local slot = 80 + (state.captureCount % 10)  -- Use slots 80-89
    emu.saveSavestate(slot)
    log(1, string.format("  Saved to slot %d", slot))
  end

  -- Clear mismatch log for next capture
  state.pMismatches = {}

  return capture
end

-- Check P register at hook entry points
local function checkPRegisterAtPC()
  local cpu = getCPUState()
  if not cpu then return end

  local pc = cpu.k * 0x10000 + cpu.pc  -- Full 24-bit PC

  for _, hook in ipairs(HOOKS) do
    if pc == hook.addr then
      local p = cpu.ps
      local m_flag = ((p & 0x20) ~= 0) and 8 or 16
      local x_flag = ((p & 0x10) ~= 0) and 8 or 16

      local mismatch = false

      if hook.expected_m and m_flag ~= hook.expected_m then
        log(1, string.format("M FLAG MISMATCH at %s (%s): expected %d-bit, got %d-bit",
          formatHex(pc, 6), hook.name, hook.expected_m, m_flag))
        table.insert(state.pMismatches, {
          pc = pc,
          hook = hook.name,
          flag = "M",
          expected = hook.expected_m,
          actual = m_flag,
        })
        mismatch = true
      end

      if hook.expected_x and x_flag ~= hook.expected_x then
        log(1, string.format("X FLAG MISMATCH at %s (%s): expected %d-bit, got %d-bit",
          formatHex(pc, 6), hook.name, hook.expected_x, x_flag))
        table.insert(state.pMismatches, {
          pc = pc,
          hook = hook.name,
          flag = "X",
          expected = hook.expected_x,
          actual = x_flag,
        })
        mismatch = true
      end

      if mismatch then
        captureState("P_REGISTER_MISMATCH")
      end

      break
    end
  end
end

-- Monitor for black screen condition
local function checkBlackScreen()
  if isScreenBlanked() and isInTransition() then
    state.blackScreenFrames = state.blackScreenFrames + 1

    if state.blackScreenFrames == CONFIG.blackScreenThreshold then
      log(0, "BLACK SCREEN DETECTED - Screen blanked for too long during transition!")
      captureState("BLACK_SCREEN_TIMEOUT")
    end
  else
    state.blackScreenFrames = 0
  end
end

-- Track transition state changes
local function trackTransitions()
  local mode = readByte(RAM.GAMEMODE)
  local submod = readByte(RAM.SUBMODULE)

  -- Detect transition start
  if not state.inTransition and isInTransition() then
    state.inTransition = true
    state.transitionStartFrame = emu.getState().ppu.frameCount or 0
    log(2, string.format("Transition started: Mode=%s, Submodule=%s",
      formatHex(mode), formatHex(submod)))
  end

  -- Detect transition end
  if state.inTransition and not isInTransition() then
    state.inTransition = false
    local duration = (emu.getState().ppu.frameCount or 0) - state.transitionStartFrame
    log(2, string.format("Transition ended after %d frames", duration))

    -- Check for anomalies after transition
    if isScreenBlanked() then
      log(1, "WARNING: Screen still blanked after transition!")
      captureState("POST_TRANSITION_BLANK")
    end
  end

  -- Track mode/submodule changes
  if mode ~= state.lastGameMode or submod ~= state.lastSubmodule then
    log(3, string.format("State change: %s/%s -> %s/%s",
      formatHex(state.lastGameMode), formatHex(state.lastSubmodule),
      formatHex(mode), formatHex(submod)))
    state.lastGameMode = mode
    state.lastSubmodule = submod
  end
end

-- Watch for writes to FADETIME (potential corruption source)
local function onFadeTimeWrite(addr, value)
  local cpu = getCPUState()
  if not cpu then return end

  local pc = cpu.k * 0x10000 + cpu.pc
  log(3, string.format("FADETIME write: %s <- %s from PC=%s",
    formatHex(addr, 6), formatHex(value, 4), formatHex(pc, 6)))

  -- Track unique writers
  table.insert(state.memWrites, {
    addr = addr,
    value = value,
    pc = pc,
    frame = emu.getState().ppu.frameCount or 0,
  })
end

-- Main frame callback
local function onFrame()
  checkPRegisterAtPC()
  checkBlackScreen()
  trackTransitions()
end

-- Initialize script
local function init()
  log(2, "=== Transition Capture Script Initialized ===")
  log(2, string.format("Black screen threshold: %d frames", CONFIG.blackScreenThreshold))
  log(2, string.format("Monitoring %d hook addresses", #HOOKS))

  -- Register callbacks
  emu.addEventCallback(onFrame, emu.eventType.endFrame)

  -- Set up memory write callbacks for FADETIME
  emu.addMemoryCallback(
    function(addr, val) onFadeTimeWrite(addr, val) end,
    emu.memCallbackType.cpuWrite,
    RAM.FADETIME
  )
  emu.addMemoryCallback(
    function(addr, val) onFadeTimeWrite(addr, val) end,
    emu.memCallbackType.cpuWrite,
    RAM.FADETIME_HI
  )

  log(2, "Callbacks registered. Monitoring active.")
end

-- Run initialization
init()
