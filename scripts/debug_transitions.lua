-- debug_transitions.lua
-- Comprehensive transition and state monitoring for Oracle of Secrets
-- Tracks module changes, room transitions, and detects potential crashes
--
-- Usage: Load in Mesen2 via Tools -> Run Script

-- =============================================================================
-- Configuration
-- =============================================================================

local CONFIG = {
  -- Logging
  logToConsole = true,
  logToFile = true,
  logFilePath = "oos_debug_log.txt",

  -- Detection thresholds
  stuckFrameThreshold = 300,    -- 5 seconds at 60fps
  loopDetectionFrames = 60,     -- Check for loops every 60 frames

  -- Display
  overlayEnabled = true,
  overlayX = 260,
  overlayY = 10,

  -- Watched memory regions for checksums
  checksumRegions = {
    { name = "COLMAPA", start = 0x7F2000, size = 0x1000 },
    { name = "WRAM_0", start = 0x7E0000, size = 0x100 },
  }
}

local logFileHandle = nil
if CONFIG.logToFile then
  local ok, handle = pcall(io.open, CONFIG.logFilePath, "w")
  if ok and handle then
    logFileHandle = handle
  else
    CONFIG.logToFile = false
    emu.log("WARN: Failed to open log file at " .. CONFIG.logFilePath)
  end
end

-- =============================================================================
-- Memory Addresses (ALTTP/OOS)
-- =============================================================================

local ADDR = {
  -- Core state
  module = 0x7E0010,        -- Main game module
  submodule = 0x7E0011,     -- Submodule
  subsubmodule = 0x7E00B0,  -- Sub-submodule

  -- Room/Area
  roomID = 0x7E00A0,        -- Current room (dungeon) or area (overworld)
  overworldArea = 0x7E008A, -- Overworld area ID
  indoors = 0x7E001B,       -- 0 = overworld, 1 = dungeon
  dungeonID = 0x7E040C,     -- Current dungeon ID

  -- Link state
  linkState = 0x7E005D,     -- Link's action state
  linkAction = 0x7E0024,    -- Link's current action
  linkPosX = 0x7E0022,      -- Link X position (16-bit)
  linkPosY = 0x7E0020,      -- Link Y position (16-bit)
  linkLayer = 0x7E00EE,     -- Link's BG layer (0 or 1)

  -- Transition state
  doorFlag = 0x7E0403,      -- Door/transition flag
  transitionDir = 0x7E0418, -- Scroll direction for transitions
  fadeState = 0x7E0046,     -- Screen fade state

  -- Stack
  stackPointer = 0x7E01FC,  -- Approximate stack region

  -- Custom (OOS)
  waterGateStates = 0x7EF411, -- Water gate persistence
  gameState = 0x7EF3C5,       -- OOS game state flag
}

-- =============================================================================
-- State Tracking
-- =============================================================================

local state = {
  frameCount = 0,

  -- Previous values for change detection
  prev = {
    module = -1,
    submodule = -1,
    roomID = -1,
    overworldArea = -1,
    indoors = -1,
    linkState = -1,
    linkPosX = -1,
    linkPosY = -1,
  },

  -- Stuck detection
  stuckCounter = 0,
  lastSignificantFrame = 0,
  positionHistory = {},

  -- Loop detection
  moduleHistory = {},

  -- Event log (circular buffer)
  eventLog = {},
  eventLogMax = 100,

  -- Checksums for change detection
  checksums = {},

  -- Crash detection
  crashDetected = false,
  crashReason = "",
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

local function timestamp()
  return string.format("[%06d]", state.frameCount)
end

local function log(message)
  local line = timestamp() .. " " .. message

  if CONFIG.logToConsole then
    emu.log(line)
  end

  if CONFIG.logToFile and logFileHandle then
    logFileHandle:write(line .. "\n")
    logFileHandle:flush()
  end

  -- Add to event log
  table.insert(state.eventLog, line)
  if #state.eventLog > state.eventLogMax then
    table.remove(state.eventLog, 1)
  end
end

local function logError(message)
  log("ERROR: " .. message)
end

local function logWarning(message)
  log("WARN: " .. message)
end

local function calculateChecksum(startAddr, size)
  local sum = 0
  for i = 0, size - 1, 64 do  -- Sample every 64 bytes for speed
    sum = sum + readByte(startAddr + i)
  end
  return sum
end

local function getModuleName(module)
  local names = {
    [0x00] = "Intro",
    [0x01] = "FileSelect",
    [0x02] = "CopyErase",
    [0x03] = "PlayerName",
    [0x04] = "LoadFile",
    [0x05] = "PreOverworld",
    [0x06] = "PreUnderworld",
    [0x07] = "Underworld",
    [0x08] = "PreOverworldLoad",
    [0x09] = "Overworld",
    [0x0A] = "OwSpecialLoad",
    [0x0B] = "OwSpecial",
    [0x0C] = "Unknown0C",
    [0x0D] = "Unknown0D",
    [0x0E] = "TextBox",
    [0x0F] = "CloseText",
    [0x10] = "Dialog",
    [0x11] = "ClosingDialog",
    [0x12] = "ItemGet",
    [0x13] = "Map",
    [0x14] = "Pause",
    [0x15] = "FileCreated",
    [0x16] = "Mirror",
    [0x17] = "Death",
    [0x18] = "BossFight",
    [0x19] = "UwDeath",
    [0x1A] = "GanonEmerge",
    [0x1B] = "Triforce",
  }
  return names[module] or string.format("Unknown_%02X", module)
end

local function getLinkStateName(linkState)
  local names = {
    [0x00] = "Ground",
    [0x01] = "Falling",
    [0x02] = "Recoil",
    [0x03] = "Spin",
    [0x04] = "Swimming",
    [0x05] = "OnLadder",
    [0x06] = "HeavyLift",
    [0x07] = "Jump",
    [0x08] = "Pull",
    [0x09] = "Push",
    [0x0A] = "Grab",
    [0x0B] = "Freeze",
    [0x0C] = "NorthBonk",
    [0x0D] = "SouthBonk",
    [0x0E] = "WestBonk",
    [0x0F] = "EastBonk",
    [0x10] = "RaftMoving",
    [0x11] = "Tree",
    [0x12] = "BeingPulled",
    [0x13] = "Hookshot",
    [0x14] = "BunnyWalk",
    [0x15] = "BunnyDash",
    [0x17] = "SmashJump",
    [0x18] = "Dashing",
    [0x19] = "DesertPray",
    [0x1A] = "Drowning",
    [0x1C] = "Pits",
    [0x1D] = "Sliding",
  }
  return names[linkState] or string.format("State_%02X", linkState)
end

-- =============================================================================
-- Change Detection
-- =============================================================================

local function checkModuleChange()
  local module = readByte(ADDR.module)
  local submodule = readByte(ADDR.submodule)

  if module ~= state.prev.module then
    log(string.format("MODULE: %s ($%02X) -> %s ($%02X)",
      getModuleName(state.prev.module), state.prev.module,
      getModuleName(module), module))
    state.prev.module = module
    state.lastSignificantFrame = state.frameCount

    -- Track for loop detection
    table.insert(state.moduleHistory, { frame = state.frameCount, module = module })
    if #state.moduleHistory > 20 then
      table.remove(state.moduleHistory, 1)
    end
  end

  if submodule ~= state.prev.submodule then
    log(string.format("  SUBMODULE: $%02X -> $%02X", state.prev.submodule, submodule))
    state.prev.submodule = submodule
    state.lastSignificantFrame = state.frameCount
  end
end

local function checkRoomChange()
  local indoors = readByte(ADDR.indoors)
  local roomID = readByte(ADDR.roomID)
  local owArea = readByte(ADDR.overworldArea)

  if indoors ~= state.prev.indoors then
    local from = state.prev.indoors == 0 and "Overworld" or "Dungeon"
    local to = indoors == 0 and "Overworld" or "Dungeon"
    log(string.format("TRANSITION: %s -> %s", from, to))
    state.prev.indoors = indoors
    state.lastSignificantFrame = state.frameCount
  end

  if indoors == 1 then
    -- Dungeon room change
    if roomID ~= state.prev.roomID then
      log(string.format("DUNGEON ROOM: $%02X -> $%02X", state.prev.roomID, roomID))
      state.prev.roomID = roomID
      state.lastSignificantFrame = state.frameCount

      -- Check collision map changes
      for _, region in ipairs(CONFIG.checksumRegions) do
        local newSum = calculateChecksum(region.start, region.size)
        local oldSum = state.checksums[region.name] or 0
        if newSum ~= oldSum then
          log(string.format("  %s checksum: %04X -> %04X", region.name, oldSum, newSum))
          state.checksums[region.name] = newSum
        end
      end
    end
  else
    -- Overworld area change
    if owArea ~= state.prev.overworldArea then
      log(string.format("OVERWORLD AREA: $%02X -> $%02X", state.prev.overworldArea, owArea))
      state.prev.overworldArea = owArea
      state.lastSignificantFrame = state.frameCount
    end
  end
end

local function checkLinkState()
  local linkState = readByte(ADDR.linkState)
  local linkX = readWord(ADDR.linkPosX)
  local linkY = readWord(ADDR.linkPosY)

  if linkState ~= state.prev.linkState then
    log(string.format("LINK STATE: %s -> %s",
      getLinkStateName(state.prev.linkState),
      getLinkStateName(linkState)))
    state.prev.linkState = linkState
    state.lastSignificantFrame = state.frameCount
  end

  -- Track position for stuck detection
  if linkX ~= state.prev.linkPosX or linkY ~= state.prev.linkPosY then
    state.prev.linkPosX = linkX
    state.prev.linkPosY = linkY
    state.lastSignificantFrame = state.frameCount
  end
end

-- =============================================================================
-- Crash/Stuck Detection
-- =============================================================================

local function checkForStuck()
  local framesSinceActivity = state.frameCount - state.lastSignificantFrame

  if framesSinceActivity > CONFIG.stuckFrameThreshold then
    if not state.crashDetected then
      state.crashDetected = true
      state.crashReason = string.format("No state change for %d frames", framesSinceActivity)
      logError("POTENTIAL CRASH/STUCK DETECTED!")
      logError(state.crashReason)
      dumpState()
    end
  else
    state.crashDetected = false
  end
end

local function checkForModuleLoop()
  if #state.moduleHistory < 10 then return end

  -- Check if we're rapidly cycling between modules
  local recent = {}
  for i = #state.moduleHistory - 5, #state.moduleHistory do
    local entry = state.moduleHistory[i]
    recent[entry.module] = (recent[entry.module] or 0) + 1
  end

  for module, count in pairs(recent) do
    if count >= 4 then
      logWarning(string.format("Module loop detected: $%02X appeared %d times in last 6 transitions",
        module, count))
    end
  end
end

local function dumpState()
  log("=== STATE DUMP ===")
  log(string.format("Module: $%02X (%s), Sub: $%02X, SubSub: $%02X",
    readByte(ADDR.module), getModuleName(readByte(ADDR.module)),
    readByte(ADDR.submodule), readByte(ADDR.subsubmodule)))
  log(string.format("Indoors: $%02X, Room: $%02X, OW Area: $%02X",
    readByte(ADDR.indoors), readByte(ADDR.roomID), readByte(ADDR.overworldArea)))
  log(string.format("Link: State=$%02X, Action=$%02X, Pos=(%d,%d), Layer=$%02X",
    readByte(ADDR.linkState), readByte(ADDR.linkAction),
    readWord(ADDR.linkPosX), readWord(ADDR.linkPosY), readByte(ADDR.linkLayer)))
  log(string.format("Door=$%02X, Scroll=$%02X, Fade=$%02X",
    readByte(ADDR.doorFlag), readByte(ADDR.transitionDir), readByte(ADDR.fadeState)))
  log(string.format("WaterGate=$%02X, GameState=$%02X",
    readByte(ADDR.waterGateStates), readByte(ADDR.gameState)))
  log("=================")
end

-- =============================================================================
-- Display Overlay
-- =============================================================================

local function drawOverlay()
  if not CONFIG.overlayEnabled then return end

  local x = CONFIG.overlayX
  local y = CONFIG.overlayY

  -- Background
  emu.drawRectangle(x - 2, y - 2, 200, 120, 0x000000, true)
  emu.drawRectangle(x - 2, y - 2, 200, 120, 0xFFFFFF, false)

  -- Title
  local titleColor = state.crashDetected and 0xFF0000 or 0x00FFFF
  emu.drawString(x, y, "=== TRANSITION DEBUG ===", titleColor)
  y = y + 12

  -- Module info
  local module = readByte(ADDR.module)
  local submodule = readByte(ADDR.submodule)
  emu.drawString(x, y, string.format("Module: %s ($%02X:%02X)",
    getModuleName(module), module, submodule), 0xFFFFFF)
  y = y + 10

  -- Location
  local indoors = readByte(ADDR.indoors)
  if indoors == 1 then
    local roomID = readByte(ADDR.roomID)
    local dungeonID = readByte(ADDR.dungeonID)
    emu.drawString(x, y, string.format("Dungeon: $%02X Room: $%02X", dungeonID, roomID), 0xFFFF00)
  else
    local owArea = readByte(ADDR.overworldArea)
    emu.drawString(x, y, string.format("Overworld Area: $%02X", owArea), 0x00FF00)
  end
  y = y + 10

  -- Link state
  local linkState = readByte(ADDR.linkState)
  emu.drawString(x, y, string.format("Link: %s ($%02X)",
    getLinkStateName(linkState), linkState), 0xFFFFFF)
  y = y + 10

  -- Position
  local linkX = readWord(ADDR.linkPosX)
  local linkY = readWord(ADDR.linkPosY)
  emu.drawString(x, y, string.format("Pos: (%d, %d)", linkX, linkY), 0x888888)
  y = y + 10

  -- Transition flags
  local doorFlag = readByte(ADDR.doorFlag)
  local transDir = readByte(ADDR.transitionDir)
  emu.drawString(x, y, string.format("Door: $%02X Scroll: $%02X", doorFlag, transDir), 0xFFFFFF)
  y = y + 10

  -- Frame counter
  local framesSinceActivity = state.frameCount - state.lastSignificantFrame
  local activityColor = framesSinceActivity > 60 and 0xFFFF00 or 0x00FF00
  if framesSinceActivity > CONFIG.stuckFrameThreshold / 2 then
    activityColor = 0xFF0000
  end
  emu.drawString(x, y, string.format("Idle: %d frames", framesSinceActivity), activityColor)
  y = y + 12

  -- Crash status
  if state.crashDetected then
    emu.drawString(x, y, "!! STUCK DETECTED !!", 0xFF0000)
  end
end

-- =============================================================================
-- Main Loop
-- =============================================================================

function Main()
  state.frameCount = state.frameCount + 1

  -- Run checks
  checkModuleChange()
  checkRoomChange()
  checkLinkState()
  checkForStuck()

  -- Periodic checks
  if state.frameCount % CONFIG.loopDetectionFrames == 0 then
    checkForModuleLoop()
  end

  -- Draw overlay
  drawOverlay()
end

-- =============================================================================
-- Initialization
-- =============================================================================

-- Initialize previous state
state.prev.module = readByte(ADDR.module)
state.prev.submodule = readByte(ADDR.submodule)
state.prev.roomID = readByte(ADDR.roomID)
state.prev.overworldArea = readByte(ADDR.overworldArea)
state.prev.indoors = readByte(ADDR.indoors)
state.prev.linkState = readByte(ADDR.linkState)
state.prev.linkPosX = readWord(ADDR.linkPosX)
state.prev.linkPosY = readWord(ADDR.linkPosY)
state.lastSignificantFrame = 0

-- Initialize checksums
for _, region in ipairs(CONFIG.checksumRegions) do
  state.checksums[region.name] = calculateChecksum(region.start, region.size)
end

emu.addEventCallback(Main, emu.eventType.endFrame)
log("Transition Debug Script loaded")
log(string.format("Initial state: Module=$%02X, Room=$%02X, OW=$%02X, Indoors=$%02X",
  state.prev.module, state.prev.roomID, state.prev.overworldArea, state.prev.indoors))
emu.displayMessage("Script", "Transition Debug Loaded - Press to toggle overlay")
