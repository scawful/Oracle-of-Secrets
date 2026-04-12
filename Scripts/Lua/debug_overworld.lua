-- debug_overworld.lua
-- Overworld-specific debugging for Oracle of Secrets
-- Tracks area transitions, scroll direction, and edge crossing
--
-- Usage: Load in Mesen2 via Tools -> Run Script

-- =============================================================================
-- Memory Addresses
-- =============================================================================

local ADDR = {
  -- Core state
  module = 0x7E0010,
  submodule = 0x7E0011,

  -- Overworld specific
  owArea = 0x7E008A,          -- Current overworld area (0x00-0x7F LW, 0x80-0xFF DW)
  owAreaPrev = 0x7E008C,      -- Previous overworld area
  indoors = 0x7E001B,         -- 0 = overworld

  -- Link position
  linkX = 0x7E0022,
  linkXHi = 0x7E0023,
  linkY = 0x7E0020,
  linkYHi = 0x7E0021,

  -- Scroll/transition
  scrollDir = 0x7E0418,       -- Scroll direction for transitions
  cameraX = 0x7E011E,
  cameraXHi = 0x7E011F,
  cameraY = 0x7E011C,
  cameraYHi = 0x7E011D,

  -- World state
  worldFlag = 0x7EF3CA,       -- Light/Dark world flag
  lightWorld = 0x7E0012,      -- Light world indicator

  -- Link state
  linkDir = 0x7E002F,         -- Link's facing direction
  fadeState = 0x7E0046,       -- Screen fade

  -- Special areas
  specialArea = 0x7E0AA8,     -- Special overworld area flag
}

-- =============================================================================
-- Direction names
-- =============================================================================

local DIRECTIONS = {
  [0x00] = "Up",
  [0x01] = "Down",
  [0x02] = "Left",
  [0x03] = "Right",
  [0x04] = "Up",
  [0x05] = "Down",
  [0x06] = "Left",
  [0x07] = "Right",
  [0x08] = "Up",
}

-- Area names (partial - just notable ones)
local AREA_NAMES = {
  [0x00] = "Lost Woods",
  [0x02] = "Kakariko",
  [0x03] = "Kakariko NE",
  [0x0A] = "Hyrule Castle",
  [0x12] = "Eastern Palace",
  [0x18] = "Death Mountain",
  [0x1B] = "Zora Domain",
  [0x1E] = "Waterfall",
  [0x22] = "Desert Palace",
  [0x2A] = "Links House",
  [0x30] = "Lake Hylia",
  [0x33] = "Lake Hylia E",
  -- DW equivalents are +0x80
}

-- =============================================================================
-- State
-- =============================================================================

local state = {
  frameCount = 0,

  -- Previous values
  prev = {
    owArea = -1,
    module = -1,
    submodule = -1,
    linkX = 0,
    linkY = 0,
    transDir = -1,
  },

  -- Transition tracking
  transitions = {},
  transitionCount = 0,
  inTransition = false,
  transitionStartFrame = 0,

  -- Edge detection
  nearEdge = false,
  edgeDir = "",

  -- Errors
  transitionErrors = {},
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

local function getAreaName(area)
  return AREA_NAMES[area] or string.format("Area_%02X", area)
end

local function getDirName(dir)
  return DIRECTIONS[dir] or string.format("Dir_%02X", dir)
end

local function log(message)
  local line = string.format("[%06d] OW: %s", state.frameCount, message)
  emu.log(line)
end

-- =============================================================================
-- Overworld Monitoring
-- =============================================================================

local function checkAreaTransition()
  local owArea = readByte(ADDR.owArea)
  local module = readByte(ADDR.module)
  local indoors = readByte(ADDR.indoors)

  -- Only monitor when on overworld
  if indoors ~= 0 then
    state.prev.owArea = -1  -- Reset when exiting overworld
    return
  end

  if owArea ~= state.prev.owArea then
    local fromName = getAreaName(state.prev.owArea)
    local toName = getAreaName(owArea)

    log(string.format("AREA: $%02X (%s) -> $%02X (%s)",
      state.prev.owArea, fromName, owArea, toName))

    -- Track transition
    state.transitionCount = state.transitionCount + 1
    table.insert(state.transitions, {
      frame = state.frameCount,
      from = state.prev.owArea,
      to = owArea,
      module = module,
    })

    -- Keep only last 20 transitions
    if #state.transitions > 20 then
      table.remove(state.transitions, 1)
    end

    -- Check for suspicious transitions
    if state.prev.owArea ~= -1 then
      local diff = math.abs(owArea - state.prev.owArea)
      -- Adjacent areas differ by 1 (horizontal) or 8 (vertical)
      if diff ~= 1 and diff ~= 8 and diff ~= 0x40 and diff ~= 0x80 then
        log(string.format("WARNING: Non-adjacent area transition! Diff=%d", diff))
        table.insert(state.transitionErrors, {
          frame = state.frameCount,
          msg = string.format("$%02X->$%02X (diff=%d)", state.prev.owArea, owArea, diff)
        })
      end
    end

    state.prev.owArea = owArea
  end
end

local function checkEdgeProximity()
  local indoors = readByte(ADDR.indoors)
  if indoors ~= 0 then
    state.nearEdge = false
    return
  end

  local linkX = readWord(ADDR.linkX)
  local linkY = readWord(ADDR.linkY)

  -- Screen is 256x224, area is typically 512x512
  -- Check if Link is near screen edge
  local localX = linkX % 256
  local localY = linkY % 224

  state.nearEdge = false
  state.edgeDir = ""

  if localX < 8 then
    state.nearEdge = true
    state.edgeDir = "Left"
  elseif localX > 248 then
    state.nearEdge = true
    state.edgeDir = "Right"
  end

  if localY < 16 then
    state.nearEdge = true
    state.edgeDir = state.edgeDir .. "Up"
  elseif localY > 200 then
    state.nearEdge = true
    state.edgeDir = state.edgeDir .. "Down"
  end
end

local function checkTransitionState()
  local module = readByte(ADDR.module)
  local submodule = readByte(ADDR.submodule)

  -- Detect transition modules (09=OW, 08/0A/0B=OW transitions)
  local isTransitionModule = (module == 0x08 or module == 0x0A or module == 0x0B)

  if isTransitionModule and not state.inTransition then
    state.inTransition = true
    state.transitionStartFrame = state.frameCount
    log(string.format("Transition START (module $%02X, sub $%02X)", module, submodule))
  elseif not isTransitionModule and state.inTransition then
    local duration = state.frameCount - state.transitionStartFrame
    log(string.format("Transition END after %d frames (now module $%02X)", duration, module))
    state.inTransition = false

    -- Warn if transition took too long
    if duration > 120 then  -- > 2 seconds
      log(string.format("WARNING: Long transition (%d frames)", duration))
    end
  end

  -- Log module changes
  if module ~= state.prev.module or submodule ~= state.prev.submodule then
    log(string.format("Module: $%02X:$%02X", module, submodule))
    state.prev.module = module
    state.prev.submodule = submodule
  end
end

-- =============================================================================
-- Overlay Display
-- =============================================================================

local function drawOverlay()
  local x = 1
  local y = 200

  -- Only draw when on overworld
  local indoors = readByte(ADDR.indoors)
  if indoors ~= 0 then return end

  -- Background
  emu.drawRectangle(x - 1, y - 1, 120, 34, 0x000000, true, 1)

  -- Area info
  local owArea = readByte(ADDR.owArea)
  local module = readByte(ADDR.module)
  local submodule = readByte(ADDR.submodule)

  emu.drawString(x, y, string.format("OW:$%02X M:$%02X:%02X", owArea, module, submodule),
    0x00FF00, 0x000000, 1)
  y = y + 10

  local scrollDir = readByte(ADDR.scrollDir)
  local linkDir = readByte(ADDR.linkDir)
  emu.drawString(x, y, string.format("Scroll:$%02X Dir:$%02X", scrollDir, linkDir),
    0xFFFFFF, 0x000000, 1)
  y = y + 10

  -- Position and edge
  local linkX = readWord(ADDR.linkX)
  local linkY = readWord(ADDR.linkY)
  local edgeColor = state.nearEdge and 0xFFFF00 or 0xFFFFFF
  emu.drawString(x, y, string.format("(%d,%d) %s", linkX, linkY, state.edgeDir),
    edgeColor, 0x000000, 1)
end

-- =============================================================================
-- Main Loop
-- =============================================================================

function Main()
  state.frameCount = state.frameCount + 1

  checkAreaTransition()
  checkEdgeProximity()
  checkTransitionState()
  drawOverlay()
end

-- =============================================================================
-- Initialization
-- =============================================================================

-- Initialize state
state.prev.owArea = readByte(ADDR.owArea)
state.prev.module = readByte(ADDR.module)
state.prev.submodule = readByte(ADDR.submodule)

emu.addEventCallback(Main, emu.eventType.endFrame)
log("Overworld Debug Script loaded")
log(string.format("Starting area: $%02X (%s)", state.prev.owArea, getAreaName(state.prev.owArea)))
emu.displayMessage("Script", "Overworld Debug Loaded")
