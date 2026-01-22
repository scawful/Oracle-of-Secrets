-- debug_crash_detector.lua
-- Advanced crash detection for Oracle of Secrets
-- Monitors hook execution, stack integrity, and invalid states
--
-- Usage: Load in Mesen2 via Tools -> Run Script

-- =============================================================================
-- Configuration
-- =============================================================================

local CONFIG = {
  -- Enable/disable specific monitors
  monitorHooks = true,
  monitorStack = true,
  monitorInvalidStates = true,
  monitorCollision = true,

  -- Overlay
  overlayEnabled = true,
  overlayX = 260,
  overlayY = 140,

  -- Thresholds
  maxStackDepth = 0x100,  -- Stack shouldn't go below $01FC - $100
}

-- =============================================================================
-- Hook Addresses (from water_collision.asm and dungeons.asm)
-- =============================================================================

local HOOKS = {
  -- Water gate fill completion hook
  waterFillHook = {
    entry = 0x01F3D2,   -- JML WaterGate_FillComplete_Hook
    exit = 0x01F3DA,    -- JML return point
    name = "WaterFill"
  },

  -- Underworld room load exit hook
  roomLoadHook = {
    entry = 0x0188DF,   -- JML Underworld_LoadRoom_ExitHook
    torchLoop = 0x0188C9, -- JML target if torches remain
    name = "RoomLoad"
  },
}

-- =============================================================================
-- Memory Addresses
-- =============================================================================

local ADDR = {
  module = 0x7E0010,
  submodule = 0x7E0011,
  roomID = 0x7E00A0,
  indoors = 0x7E001B,
  linkPosX = 0x7E0022,
  linkPosY = 0x7E0020,

  -- CPU state (via callback)
  stackPointer = 0x7E01FF,  -- Stack grows down from here

  -- Scratch memory used by hooks
  scratch00 = 0x7E0000,
  scratch04 = 0x7E0004,

  -- Data bank register area
  dataBank = 0x7E006C,  -- Approximate - actual DB is in CPU

  -- Collision maps
  colmapA = 0x7F2000,
  colmapB = 0x7F3000,

  -- OOS specific
  waterGateStates = 0x7EF411,
}

-- Valid module values
local VALID_MODULES = {
  [0x00] = true, [0x01] = true, [0x02] = true, [0x03] = true,
  [0x04] = true, [0x05] = true, [0x06] = true, [0x07] = true,
  [0x08] = true, [0x09] = true, [0x0A] = true, [0x0B] = true,
  [0x0C] = true, [0x0D] = true, [0x0E] = true, [0x0F] = true,
  [0x10] = true, [0x11] = true, [0x12] = true, [0x13] = true,
  [0x14] = true, [0x15] = true, [0x16] = true, [0x17] = true,
  [0x18] = true, [0x19] = true, [0x1A] = true, [0x1B] = true,
}

-- =============================================================================
-- State
-- =============================================================================

local state = {
  frameCount = 0,

  -- Hook tracking
  hookHits = {},
  lastHookHit = "",
  hookErrors = {},

  -- Stack tracking
  stackMin = 0x01FF,
  stackWarnings = 0,
  stackSupported = nil,

  -- Error log
  errors = {},
  maxErrors = 20,

  -- Collision integrity
  lastColmapChecksum = 0,
  colmapCorruption = false,

  -- Detection flags
  invalidModuleDetected = false,
  stackOverflow = false,
  hookMismatch = false,
}

-- =============================================================================
-- Utility Functions
-- =============================================================================

local function readByte(addr)
  return emu.read(addr, emu.memType.snesMemory)
end

local function readWord(addr)
  return readByte(addr) + (readByte(addr + 1) * 256)
end

local function readStackPointer()
  local ok, sp = pcall(function() return emu.getRegister("S") end)
  if ok then
    return sp
  end
  return nil
end

local function log(message)
  local line = string.format("[%06d] %s", state.frameCount, message)
  emu.log(line)
  table.insert(state.errors, line)
  if #state.errors > state.maxErrors then
    table.remove(state.errors, 1)
  end
end

local function logError(message)
  log("CRASH: " .. message)
end

-- =============================================================================
-- Hook Execution Monitor
-- =============================================================================

-- Track when we enter/exit hooks via exec callbacks
local function onWaterFillHookEntry()
  state.lastHookHit = "WaterFill_Entry"
  state.hookHits["WaterFill_Entry"] = (state.hookHits["WaterFill_Entry"] or 0) + 1
  log("HOOK: WaterFill entry")

  -- Verify we're in a valid state for this hook
  local module = readByte(ADDR.module)
  if module ~= 0x07 then  -- Should be in underworld module
    logError(string.format("WaterFill hook called in wrong module: $%02X (expected $07)", module))
    state.hookErrors["WaterFill"] = "Wrong module"
  end
end

local function onWaterFillHookExit()
  state.lastHookHit = "WaterFill_Exit"
  state.hookHits["WaterFill_Exit"] = (state.hookHits["WaterFill_Exit"] or 0) + 1
  log("HOOK: WaterFill exit")
end

local function onRoomLoadHookEntry()
  state.lastHookHit = "RoomLoad_Entry"
  state.hookHits["RoomLoad_Entry"] = (state.hookHits["RoomLoad_Entry"] or 0) + 1
  -- Don't log every room load - too noisy
end

local function onRoomLoadTorchLoop()
  state.lastHookHit = "RoomLoad_TorchLoop"
  state.hookHits["RoomLoad_TorchLoop"] = (state.hookHits["RoomLoad_TorchLoop"] or 0) + 1
end

-- =============================================================================
-- Invalid State Detection
-- =============================================================================

local function checkInvalidStates()
  if not CONFIG.monitorInvalidStates then return end

  -- Check for invalid module
  local module = readByte(ADDR.module)
  if not VALID_MODULES[module] then
    if not state.invalidModuleDetected then
      logError(string.format("Invalid module value: $%02X", module))
      state.invalidModuleDetected = true
    end
  else
    state.invalidModuleDetected = false
  end

  -- Check for Link at invalid position (0,0 usually means corruption)
  local linkX = readWord(ADDR.linkPosX)
  local linkY = readWord(ADDR.linkPosY)
  if linkX == 0 and linkY == 0 then
    local module = readByte(ADDR.module)
    -- Only warn if we're in gameplay modules
    if module == 0x07 or module == 0x09 then
      log(string.format("WARNING: Link at (0,0) in module $%02X", module))
    end
  end

  -- Check for room ID out of expected range when indoors
  local indoors = readByte(ADDR.indoors)
  local roomID = readByte(ADDR.roomID)
  if indoors == 1 and roomID > 0x80 then
    log(string.format("WARNING: High room ID $%02X while indoors", roomID))
  end
end

-- =============================================================================
-- Collision Map Integrity
-- =============================================================================

local function checkCollisionIntegrity()
  if not CONFIG.monitorCollision then return end

  -- Only check periodically (expensive)
  if state.frameCount % 30 ~= 0 then return end

  -- Quick checksum of collision map header area
  local sum = 0
  for i = 0, 0xFF do
    sum = sum + readByte(ADDR.colmapA + i)
  end

  if state.lastColmapChecksum ~= 0 and sum ~= state.lastColmapChecksum then
    local module = readByte(ADDR.module)
    local roomID = readByte(ADDR.roomID)
    log(string.format("COLMAP changed: %04X -> %04X (Module $%02X, Room $%02X)",
      state.lastColmapChecksum, sum, module, roomID))
  end

  state.lastColmapChecksum = sum
end

local function checkStackIntegrity()
  if not CONFIG.monitorStack then return end

  local sp = readStackPointer()
  if sp == nil then
    state.stackSupported = false
    CONFIG.monitorStack = false
    return
  end

  state.stackSupported = true
  if sp < state.stackMin then
    state.stackMin = sp
  end

  local stackLimit = 0x01FF - CONFIG.maxStackDepth
  state.stackOverflow = sp < stackLimit
end

-- =============================================================================
-- Overlay Display
-- =============================================================================

local function drawOverlay()
  if not CONFIG.overlayEnabled then return end

  local x = CONFIG.overlayX
  local y = CONFIG.overlayY

  -- Background
  emu.drawRectangle(x - 2, y - 2, 200, 85, 0x000000, true)
  emu.drawRectangle(x - 2, y - 2, 200, 85, 0xFF8800, false)

  -- Title
  local hasErrors = #state.errors > 0
  local titleColor = hasErrors and 0xFF0000 or 0xFF8800
  emu.drawString(x, y, "=== CRASH DETECTOR ===", titleColor)
  y = y + 12

  -- Last hook
  emu.drawString(x, y, string.format("Last Hook: %s", state.lastHookHit or "none"), 0xFFFFFF)
  y = y + 10

  -- Hook counts
  local waterEntry = state.hookHits["WaterFill_Entry"] or 0
  local waterExit = state.hookHits["WaterFill_Exit"] or 0
  local roomEntry = state.hookHits["RoomLoad_Entry"] or 0
  emu.drawString(x, y, string.format("WaterHook: %d/%d  RoomHook: %d",
    waterEntry, waterExit, roomEntry), 0x888888)
  y = y + 10

  -- Stack depth
  if CONFIG.monitorStack and state.stackSupported then
    emu.drawString(x, y, string.format("Stack min: $%04X", state.stackMin),
      state.stackOverflow and 0xFF0000 or 0x00FF00)
  else
    emu.drawString(x, y, "Stack: N/A", 0x888888)
  end
  y = y + 10

  -- Collision status
  emu.drawString(x, y, string.format("ColMap: $%04X", state.lastColmapChecksum), 0xFFFFFF)
  y = y + 10

  -- Error count
  if hasErrors then
    emu.drawString(x, y, string.format("Errors: %d (check log)", #state.errors), 0xFF0000)
  else
    emu.drawString(x, y, "Status: OK", 0x00FF00)
  end
end

-- =============================================================================
-- Main Loop
-- =============================================================================

function Main()
  state.frameCount = state.frameCount + 1

  checkInvalidStates()
  checkCollisionIntegrity()
  checkStackIntegrity()
  drawOverlay()
end

-- =============================================================================
-- Initialization
-- =============================================================================

-- Register execution callbacks for hook monitoring
if CONFIG.monitorHooks then
  -- Note: These may not work in all Mesen versions - depends on exec callback support
  -- For now, we rely on state-based detection

  -- Attempt to register (will silently fail if not supported)
  pcall(function()
    emu.addMemoryCallback(onWaterFillHookEntry, emu.callbackType.exec, HOOKS.waterFillHook.entry)
    emu.addMemoryCallback(onWaterFillHookExit, emu.callbackType.exec, HOOKS.waterFillHook.exit)
    emu.addMemoryCallback(onRoomLoadHookEntry, emu.callbackType.exec, HOOKS.roomLoadHook.entry)
    emu.addMemoryCallback(onRoomLoadTorchLoop, emu.callbackType.exec, HOOKS.roomLoadHook.torchLoop)
  end)
end

emu.addEventCallback(Main, emu.eventType.endFrame)
log("Crash Detector Script loaded")
emu.displayMessage("Script", "Crash Detector Loaded")
