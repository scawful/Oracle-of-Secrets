-- ============================================================================
-- Oracle of Secrets - Unified Mesen2 Bridge
-- ============================================================================
-- Single script for all debugging, monitoring, and CLI communication
-- Consolidates: mesen_live_bridge, debug_crash_detector, debug_transitions
--
-- Features:
--   - CLI bridge for external tool communication
--   - Crash/stuck detection
--   - Transition monitoring and logging
--   - Input injection
--   - Save state management with SRAM preservation
--   - Debug overlay (toggleable)
--
-- Usage: Load in Mesen2 via Tools -> Run Script (or auto-load)
-- ============================================================================

-- =============================================================================
-- Configuration
-- =============================================================================

local CONFIG = {
    -- Debug features (toggle these)
    enableCrashDetection = true,
    enableTransitionLog = true,
    enableOverlay = true,
    enableHookMonitor = true,

    -- Overlay settings
    overlayX = 2,
    overlayY = 2,
    overlayWidth = 120,

    -- Crash detection thresholds
    stuckFrameThreshold = 300,    -- 5 seconds at 60fps
    maxStackDepth = 0x100,

    -- Logging
    logToConsole = true,
    logTransitions = true,
}

-- =============================================================================
-- Bridge Paths (auto-configured)
-- =============================================================================

local function getScriptPath()
    local info = debug.getinfo(1, "S")
    if info and info.source then
        local src = info.source
        if src:sub(1, 1) == "@" then
            return src:sub(2)
        end
    end
    return nil
end

local function loadConfig(path)
    if not path then return {} end
    local f = io.open(path, "r")
    if not f then return {} end
    local raw = f:read("*all") or ""
    f:close()
    local cfg = {}
    local function grab(key)
        local pattern = '"' .. key .. '"%s*:%s*"([^"]*)"'
        local val = raw:match(pattern)
        if val then cfg[key] = val end
    end
    grab("bridge_dir")
    grab("instance_id")
    return cfg
end

local scriptPath = getScriptPath()
local scriptDir = scriptPath and scriptPath:match("(.+)/[^/]+$") or (os.getenv("HOME") .. "/Documents/Mesen2/Scripts")
local configPath = scriptPath and (scriptPath .. ".json") or nil
local config = configPath and loadConfig(configPath) or {}

if not config.bridge_dir or not config.instance_id then
    local fallback = loadConfig(scriptDir .. "/bridge_config.json")
    for k, v in pairs(fallback) do
        if config[k] == nil then config[k] = v end
    end
end

local BRIDGE_DIR = os.getenv("MESEN_BRIDGE_DIR") or config.bridge_dir or (os.getenv("HOME") .. "/Documents/Mesen2/bridge")
local INSTANCE_ID = os.getenv("MESEN_INSTANCE_ID") or config.instance_id or "default"
local STATE_FILE = BRIDGE_DIR .. "/state.json"
local CMD_FILE = BRIDGE_DIR .. "/command.txt"
local RESPONSE_FILE = BRIDGE_DIR .. "/response.txt"
local WATCH_FILE = BRIDGE_DIR .. "/watchlist.txt"
local LOG_DIR = BRIDGE_DIR .. "/logs"
local TRACE_PATH = LOG_DIR .. "/write_trace.jsonl"

-- =============================================================================
-- Memory Addresses
-- =============================================================================

local ADDR = {
    -- Core state
    module = 0x7E0010,
    submodule = 0x7E0011,
    subsubmodule = 0x7E00B0,
    frame = 0x7E001A,
    indoors = 0x7E001B,

    -- Room/Area
    roomID = 0x7E00A0,
    overworldArea = 0x7E008A,
    dungeonID = 0x7E040C,

    -- Link state
    linkState = 0x7E005D,
    linkAction = 0x7E0024,
    linkPosX = 0x7E0022,
    linkPosY = 0x7E0020,
    linkDir = 0x7E002F,
    linkLayer = 0x7E00EE,

    -- Input registers
    inputF4 = 0x7E00F4,
    inputF6 = 0x7E00F6,
    inputF2 = 0x7E00F2,

    -- Transition
    doorFlag = 0x7E0403,
    transitionDir = 0x7E0418,
    fadeState = 0x7E0046,

    -- Equipment
    equippedSlot = 0x7E0202,
    goldstarOrHookshot = 0x7E0739,

    -- Collision maps
    colmapA = 0x7F2000,
    colmapB = 0x7F3000,

    -- Debug reinit (custom OOS WRAM)
    reinitFlags = 0x7E0746,
    reinitStatus = 0x7E0747,
    reinitError = 0x7E0748,
    reinitSeq = 0x7E0749,
    reinitLast = 0x7E074A,

    -- SRAM
    sramBase = 0x7EF300,
    health = 0x7EF36D,
    maxHealth = 0x7EF36C,
    moonPearl = 0x7EF357,
    flute = 0x7EF34C,
    sword = 0x7EF359,
    shield = 0x7EF35A,
    gloves = 0x7EF354,
    boots = 0x7EF355,
    flippers = 0x7EF356,
    waterGateStates = 0x7EF411,
    gameState = 0x7EF3C5,
}

local REINIT_TARGETS = {
    dialog = 0x01, sprites = 0x02, overlays = 0x04, msgbank = 0x08, roomcache = 0x10,
}

-- Valid module values for crash detection
local VALID_MODULES = {}
for i = 0x00, 0x1B do VALID_MODULES[i] = true end

-- Button mappings for input injection
local BUTTONS = {
    UP = {reg = "f4", bit = 0x08}, DOWN = {reg = "f4", bit = 0x04},
    LEFT = {reg = "f4", bit = 0x02}, RIGHT = {reg = "f4", bit = 0x01},
    SELECT = {reg = "f4", bit = 0x20}, START = {reg = "f4", bit = 0x10},
    B = {reg = "f4", bit = 0x80}, Y = {reg = "f4", bit = 0x40},
    A = {reg = "f6", bit = 0x80}, X = {reg = "f6", bit = 0x40},
    L = {reg = "f6", bit = 0x20}, R = {reg = "f6", bit = 0x10},
}

-- =============================================================================
-- State
-- =============================================================================

local state = {
    frameCount = 0,

    -- Previous values for transition detection
    prev = {
        module = -1, submodule = -1, roomID = -1,
        overworldArea = -1, indoors = -1, linkState = -1,
        linkPosX = -1, linkPosY = -1,
    },

    -- Crash detection
    lastSignificantFrame = 0,
    crashDetected = false,
    crashReason = "",
    invalidModuleDetected = false,
    stackMin = 0x01FF,
    stackOverflow = false,

    -- Hook tracking
    hookHits = {},
    lastHookHit = "",

    -- Collision checksum
    lastColmapChecksum = 0,

    -- Module history for loop detection
    moduleHistory = {},

    -- Event log
    eventLog = {},
    eventLogMax = 50,

    -- Savestate management
    savestatePending = nil,
    savestateStatus = "idle",
    savestateError = "",
    savestateLastPath = "",
    savePendingSlot = nil,
    savePendingPath = nil,

    -- Preserve list for save states
    preserveList = {
        0x7EF357, 0x7EF34C, 0x7EF359, 0x7EF35A,
        0x7EF354, 0x7EF355, 0x7EF356,
    },
    preserveEnabled = true,
    preservedValues = {},

    -- Input injection
    injectedInput = { f4 = 0, f6 = 0, frames = 0, active = false },

    -- Watch list
    watchlist = {},
    watchlistRaw = "",

    -- Logging
    logActive = false,
    logPath = LOG_DIR .. "/state_log.jsonl",
    logEvery = 60,
    traceActive = false,
}

-- =============================================================================
-- Utility Functions
-- =============================================================================

local function read8(addr)
    return emu.read(addr, emu.memType.snesMemory)
end

local function read16(addr)
    return read8(addr) + (read8(addr + 1) * 256)
end

local function write8(addr, value)
    emu.write(addr, value & 0xFF, emu.memType.snesMemory)
end

local function write16(addr, value)
    write8(addr, value)
    write8(addr + 1, math.floor(value / 256))
end

local function parseAddr(value)
    if value == nil then return nil end
    if type(value) == "number" then return value end
    local s = tostring(value):gsub("^%s+", ""):gsub("%s+$", "")
    if s:sub(1, 2):lower() == "0x" then
        return tonumber(s:sub(3), 16)
    end
    return tonumber(s)
end

local function log(message)
    local line = string.format("[%06d] %s", state.frameCount, message)
    if CONFIG.logToConsole then
        emu.log(line)
    end
    table.insert(state.eventLog, line)
    if #state.eventLog > state.eventLogMax then
        table.remove(state.eventLog, 1)
    end
end

local function readStackPointer()
    local ok, sp = pcall(function() return emu.getRegister("S") end)
    return ok and sp or nil
end

-- Module name lookup
local MODULE_NAMES = {
    [0x00] = "Intro", [0x01] = "FileSelect", [0x02] = "CopyErase",
    [0x03] = "PlayerName", [0x04] = "LoadFile", [0x05] = "PreOverworld",
    [0x06] = "PreUnderworld", [0x07] = "Underworld", [0x08] = "PreOwLoad",
    [0x09] = "Overworld", [0x0A] = "OwSpecLoad", [0x0B] = "OwSpecial",
    [0x0E] = "TextBox", [0x0F] = "CloseText", [0x10] = "Dialog",
    [0x11] = "CloseDialog", [0x12] = "ItemGet", [0x13] = "Map",
    [0x14] = "Pause", [0x17] = "Death", [0x18] = "BossFight",
}

local function getModuleName(module)
    return MODULE_NAMES[module] or string.format("$%02X", module)
end

-- Link state name lookup
local LINK_STATE_NAMES = {
    [0x00] = "Ground", [0x01] = "Falling", [0x02] = "Recoil",
    [0x04] = "Swimming", [0x14] = "BunnyWalk", [0x18] = "Dashing",
}

local function getLinkStateName(ls)
    return LINK_STATE_NAMES[ls] or string.format("$%02X", ls)
end

-- =============================================================================
-- Transition Monitoring
-- =============================================================================

local function checkTransitions()
    if not CONFIG.enableTransitionLog then return end

    local module = read8(ADDR.module)
    local submodule = read8(ADDR.submodule)
    local indoors = read8(ADDR.indoors)
    local roomID = read8(ADDR.roomID)
    local owArea = read8(ADDR.overworldArea)
    local linkState = read8(ADDR.linkState)
    local linkX = read16(ADDR.linkPosX)
    local linkY = read16(ADDR.linkPosY)

    -- Module change
    if module ~= state.prev.module then
        if CONFIG.logTransitions then
            log(string.format("MODULE: %s -> %s",
                getModuleName(state.prev.module), getModuleName(module)))
        end
        state.prev.module = module
        state.lastSignificantFrame = state.frameCount

        -- Track for loop detection
        table.insert(state.moduleHistory, { frame = state.frameCount, module = module })
        if #state.moduleHistory > 20 then table.remove(state.moduleHistory, 1) end
    end

    -- Submodule change
    if submodule ~= state.prev.submodule then
        state.prev.submodule = submodule
        state.lastSignificantFrame = state.frameCount
    end

    -- Indoor/outdoor transition
    if indoors ~= state.prev.indoors then
        if CONFIG.logTransitions then
            local from = state.prev.indoors == 0 and "Overworld" or "Dungeon"
            local to = indoors == 0 and "Overworld" or "Dungeon"
            log(string.format("TRANSITION: %s -> %s", from, to))
        end
        state.prev.indoors = indoors
        state.lastSignificantFrame = state.frameCount
    end

    -- Room change (dungeon)
    if indoors == 1 and roomID ~= state.prev.roomID then
        if CONFIG.logTransitions then
            log(string.format("ROOM: $%02X -> $%02X", state.prev.roomID, roomID))
        end
        state.prev.roomID = roomID
        state.lastSignificantFrame = state.frameCount
    end

    -- Overworld area change
    if indoors == 0 and owArea ~= state.prev.overworldArea then
        if CONFIG.logTransitions then
            log(string.format("OW AREA: $%02X -> $%02X", state.prev.overworldArea, owArea))
        end
        state.prev.overworldArea = owArea
        state.lastSignificantFrame = state.frameCount
    end

    -- Link state change
    if linkState ~= state.prev.linkState then
        state.prev.linkState = linkState
        state.lastSignificantFrame = state.frameCount
    end

    -- Position change
    if linkX ~= state.prev.linkPosX or linkY ~= state.prev.linkPosY then
        state.prev.linkPosX = linkX
        state.prev.linkPosY = linkY
        state.lastSignificantFrame = state.frameCount
    end
end

-- =============================================================================
-- Crash Detection
-- =============================================================================

local function checkCrashConditions()
    if not CONFIG.enableCrashDetection then return end

    -- Check for invalid module
    local module = read8(ADDR.module)
    if not VALID_MODULES[module] then
        if not state.invalidModuleDetected then
            log(string.format("CRASH: Invalid module $%02X", module))
            state.invalidModuleDetected = true
            state.crashDetected = true
            state.crashReason = "Invalid module"
        end
    else
        state.invalidModuleDetected = false
    end

    -- Check for stuck state
    local framesSinceActivity = state.frameCount - state.lastSignificantFrame
    if framesSinceActivity > CONFIG.stuckFrameThreshold then
        if not state.crashDetected then
            state.crashDetected = true
            state.crashReason = string.format("Stuck %d frames", framesSinceActivity)
            log("CRASH: " .. state.crashReason)
        end
    elseif state.crashReason:find("Stuck") then
        state.crashDetected = false
        state.crashReason = ""
    end

    -- Check stack (if supported)
    local sp = readStackPointer()
    if sp then
        if sp < state.stackMin then state.stackMin = sp end
        local limit = 0x01FF - CONFIG.maxStackDepth
        if sp < limit then
            state.stackOverflow = true
            if not state.crashDetected then
                state.crashDetected = true
                state.crashReason = string.format("Stack overflow SP=$%04X", sp)
                log("CRASH: " .. state.crashReason)
            end
        end
    end

    -- Check collision map integrity (every 30 frames)
    if state.frameCount % 30 == 0 then
        local sum = 0
        for i = 0, 0xFF do sum = sum + read8(ADDR.colmapA + i) end
        if state.lastColmapChecksum ~= 0 and sum ~= state.lastColmapChecksum then
            local module = read8(ADDR.module)
            -- Only warn if not in transition
            if module == 0x07 or module == 0x09 then
                log(string.format("COLMAP changed: %04X -> %04X", state.lastColmapChecksum, sum))
            end
        end
        state.lastColmapChecksum = sum
    end
end

-- =============================================================================
-- Debug Overlay
-- =============================================================================

local function drawOverlay()
    if not CONFIG.enableOverlay then return end

    local x, y = CONFIG.overlayX, CONFIG.overlayY
    local w = CONFIG.overlayWidth

    -- Background
    emu.drawRectangle(x, y, w, 82, 0x000000, true)
    emu.drawRectangle(x, y, w, 82, state.crashDetected and 0xFF0000 or 0x00AAFF, false)

    x, y = x + 2, y + 2

    -- Title
    emu.drawString(x, y, "OOS Bridge", state.crashDetected and 0xFF0000 or 0x00FFFF)
    y = y + 10

    -- Module/Room
    local module = read8(ADDR.module)
    local submodule = read8(ADDR.submodule)
    local indoors = read8(ADDR.indoors)
    emu.drawString(x, y, string.format("M:%s S:%02X", getModuleName(module), submodule), 0xFFFFFF)
    y = y + 9

    if indoors == 1 then
        emu.drawString(x, y, string.format("Room: $%02X", read8(ADDR.roomID)), 0xFFFF00)
    else
        emu.drawString(x, y, string.format("OW: $%02X", read8(ADDR.overworldArea)), 0x00FF00)
    end
    y = y + 9

    -- Link position
    emu.drawString(x, y, string.format("(%d,%d)", read16(ADDR.linkPosX), read16(ADDR.linkPosY)), 0x888888)
    y = y + 9

    -- Idle frames
    local idle = state.frameCount - state.lastSignificantFrame
    local idleColor = idle > 60 and (idle > 150 and 0xFF0000 or 0xFFFF00) or 0x00FF00
    emu.drawString(x, y, string.format("Idle: %d", idle), idleColor)
    y = y + 9

    -- Bridge status
    local bridgeStatus = state.savestateStatus ~= "idle" and state.savestateStatus or "ready"
    emu.drawString(x, y, string.format("Br: %s", bridgeStatus), 0xAAAAAA)
    y = y + 10

    -- Crash status
    if state.crashDetected then
        emu.drawString(x, y, state.crashReason:sub(1, 18), 0xFF0000)
    else
        emu.drawString(x, y, "Status: OK", 0x00FF00)
    end
end

-- =============================================================================
-- Input Injection
-- =============================================================================

local function parseButtons(btnStr)
    local f4, f6 = 0, 0
    for btn in btnStr:upper():gmatch("[^+]+") do
        btn = btn:gsub("^%s+", ""):gsub("%s+$", "")
        local m = BUTTONS[btn]
        if m then
            if m.reg == "f4" then f4 = f4 | m.bit else f6 = f6 | m.bit end
        end
    end
    return f4, f6
end

local function applyInjectedInput()
    local inp = state.injectedInput
    if not inp.active then return end

    if inp.frames > 0 then
        if inp.f4 ~= 0 then
            write8(ADDR.inputF4, read8(ADDR.inputF4) | inp.f4)
        end
        if inp.f6 ~= 0 then
            write8(ADDR.inputF6, read8(ADDR.inputF6) | inp.f6)
            write8(ADDR.inputF2, read8(ADDR.inputF2) | inp.f6)
        end
        inp.frames = inp.frames - 1
    else
        inp.active = false
        inp.f4, inp.f6 = 0, 0
    end
end

-- =============================================================================
-- Save State Management
-- =============================================================================

local function snapshotPreservedValues()
    state.preservedValues = {}
    if not state.preserveEnabled then return end
    for _, addr in ipairs(state.preserveList) do
        state.preservedValues[addr] = read8(addr)
    end
end

local function restorePreservedValues()
    if not state.preserveEnabled then return end
    for addr, val in pairs(state.preservedValues) do
        if val and val > 0 then write8(addr, val) end
    end
    state.preservedValues = {}
end

local function loadSavestateNow()
    if not state.savestatePending then return end
    local path = state.savestatePending
    state.savestatePending = nil

    local f = io.open(path, "rb")
    if not f then
        state.savestateStatus = "error"
        state.savestateError = "file_not_found"
        return
    end
    local data = f:read("*all")
    f:close()

    snapshotPreservedValues()
    local ok, result = pcall(emu.loadSavestate, data)
    if ok and result then
        restorePreservedValues()
        state.savestateStatus = "ok"
        state.savestateError = ""
    else
        state.savestateStatus = "error"
        state.savestateError = ok and "load_failed" or tostring(result)
    end
end

local function saveSavestateNow()
    if not state.savePendingPath then return end
    local path = state.savePendingPath
    state.savePendingSlot = nil
    state.savePendingPath = nil

    local ok, data = pcall(emu.createSavestate)
    if ok and data and #data > 0 then
        local sf = io.open(path, "wb")
        if sf then
            sf:write(data)
            sf:close()
            state.savestateStatus = "saved"
            state.savestateLastPath = path
            state.savestateError = ""
        else
            state.savestateStatus = "error"
            state.savestateError = "write_failed"
        end
    else
        state.savestateStatus = "error"
        state.savestateError = "create_failed"
    end
end

-- =============================================================================
-- State JSON
-- =============================================================================

local function getStateJSON()
    local s = {
        timestamp = os.time(),
        frame = state.frameCount,
        mode = read8(ADDR.module),
        submode = read8(ADDR.submodule),
        indoors = read8(ADDR.indoors) == 1,
        roomId = read8(ADDR.roomID),
        overworldArea = read8(ADDR.overworldArea),
        linkState = read8(ADDR.linkState),
        linkX = read16(ADDR.linkPosX),
        linkY = read16(ADDR.linkPosY),
        linkDir = read8(ADDR.linkDir),
        health = read8(ADDR.health),
        maxHealth = read8(ADDR.maxHealth),
        inputF4 = read8(ADDR.inputF4),
        inputF6 = read8(ADDR.inputF6),
        savestateStatus = state.savestateStatus,
        savestateError = state.savestateError,
        savestateLastPath = state.savestateLastPath,
        crashDetected = state.crashDetected,
        crashReason = state.crashReason,
        idleFrames = state.frameCount - state.lastSignificantFrame,
        instanceId = INSTANCE_ID,
    }

    -- Build JSON string
    local lines = {"{"}
    for k, v in pairs(s) do
        local val
        if type(v) == "boolean" then val = v and "true" or "false"
        elseif type(v) == "number" then val = tostring(v)
        elseif type(v) == "string" then val = '"' .. v:gsub('"', '\\"') .. '"'
        else val = "null" end
        lines[#lines + 1] = string.format('  "%s": %s,', k, val)
    end
    lines[#lines] = lines[#lines]:sub(1, -2) -- Remove trailing comma
    lines[#lines + 1] = "}"
    return table.concat(lines, "\n")
end

local function writeState()
    local json = getStateJSON()
    local tmp = STATE_FILE .. ".tmp"
    local f = io.open(tmp, "w")
    if f then
        f:write(json)
        f:close()
        os.rename(tmp, STATE_FILE)
    end
end

-- =============================================================================
-- Command Processing
-- =============================================================================

local function processCommands()
    local f = io.open(CMD_FILE, "r")
    if not f then return end
    local content = f:read("*all")
    f:close()
    content = content:gsub("^%s+", ""):gsub("%s+$", "")
    if content == "" then return end

    -- Parse: "id|CMD|arg1|arg2" or legacy "CMD:arg1:arg2"
    local parts = {}
    local responseMode = "legacy"
    local reqId = nil

    if content:find("|", 1, true) then
        for part in content:gmatch("[^|]+") do parts[#parts + 1] = part end
        reqId = parts[1]
        responseMode = "pipe"
    else
        for part in content:gmatch("[^:]+") do parts[#parts + 1] = part end
    end

    local cmd = (responseMode == "pipe" and parts[2] or parts[1]) or ""
    cmd = cmd:upper()
    local arg1 = responseMode == "pipe" and parts[3] or parts[2]
    local arg2 = responseMode == "pipe" and parts[4] or parts[3]
    local arg3 = responseMode == "pipe" and parts[5] or parts[4]

    local response = ""
    local responseOk = true

    -- Command handlers
    if cmd == "READ" and arg1 then
        local addr = parseAddr(arg1)
        if addr then
            local val = read8(addr)
            response = string.format("READ:0x%06X=0x%02X (%d)", addr, val, val)
        end
    elseif cmd == "READ16" and arg1 then
        local addr = parseAddr(arg1)
        if addr then
            local val = read16(addr)
            response = string.format("READ16:0x%06X=0x%04X (%d)", addr, val, val)
        end
    elseif cmd == "WRITE" and arg1 and arg2 then
        local addr, val = parseAddr(arg1), parseAddr(arg2)
        if addr and val then
            write8(addr, val)
            response = string.format("WRITE:0x%06X=0x%02X", addr, val % 256)
        end
    elseif cmd == "WRITE16" and arg1 and arg2 then
        local addr, val = parseAddr(arg1), parseAddr(arg2)
        if addr and val then
            write16(addr, val)
            response = string.format("WRITE16:0x%06X=0x%04X", addr, val % 65536)
        end
    elseif cmd == "STATE" then
        response = getStateJSON()
    elseif cmd == "PING" then
        response = "PONG:" .. os.time()
    elseif cmd == "INPUT" or cmd == "PRESS" then
        local buttons = arg1
        local frames = parseAddr(arg2) or 5
        if buttons then
            local f4, f6 = parseButtons(buttons)
            state.injectedInput = { f4 = f4, f6 = f6, frames = frames, active = true }
            response = string.format("INPUT:buttons=%s,f4=0x%02X,f6=0x%02X,frames=%d", buttons, f4, f6, frames)
        else
            responseOk = false
            response = "INPUT:error=no_buttons"
        end
    elseif cmd == "RELEASE" then
        state.injectedInput = { f4 = 0, f6 = 0, frames = 0, active = false }
        response = "RELEASE:ok"
    elseif cmd == "LOADSTATE" then
        local path = arg1
        if path then
            path = path:gsub("^%s+", ""):gsub("%s+$", "")
            state.savestatePending = path
            state.savestateStatus = "pending"
            state.savestateLastPath = path
            response = "LOADSTATE:queued:" .. path
        else
            responseOk = false
            response = "LOADSTATE:error=missing_path"
        end
    elseif cmd == "LOADSLOT" then
        local slot = parseAddr(arg1)
        if slot and slot >= 1 and slot <= 10 then
            local path = os.getenv("HOME") .. "/Documents/Mesen2/SaveStates/oos168x_" .. slot .. ".mss"
            state.savestatePending = path
            state.savestateStatus = "pending"
            state.savestateLastPath = path
            response = string.format("LOADSLOT:queued,slot=%d", slot)
        else
            responseOk = false
            response = "LOADSLOT:error=invalid_slot"
        end
    elseif cmd == "SAVESTATE" or cmd == "SAVESLOT" then
        local slot = parseAddr(arg1)
        if slot and slot >= 1 and slot <= 10 then
            state.savePendingSlot = slot
            state.savePendingPath = os.getenv("HOME") .. "/Documents/Mesen2/SaveStates/oos168x_" .. slot .. ".mss"
            state.savestateStatus = "pending"
            response = string.format("SAVESTATE:queued,slot=%d", slot)
        else
            responseOk = false
            response = "SAVESTATE:error=invalid_slot"
        end
    elseif cmd == "SCREENSHOT" then
        local path = arg1 or (BRIDGE_DIR .. "/screenshot_" .. os.time() .. ".png")
        local ok, result = pcall(emu.takeScreenshot, path)
        if not ok then ok, result = pcall(emu.takeScreenshot) end
        response = ok and ("SCREENSHOT:" .. (result or path)) or ("SCREENSHOT:error=" .. tostring(result))
        responseOk = ok
    elseif cmd == "PAUSE" then
        local ok = pcall(emu.pause) or pcall(emu.breakExecution)
        response = ok and "PAUSE:ok" or "PAUSE:error"
        responseOk = ok
    elseif cmd == "RESUME" then
        local ok = pcall(emu.resume) or pcall(function() emu.setPaused(false) end)
        response = ok and "RESUME:ok" or "RESUME:error"
        responseOk = ok
    elseif cmd == "RESET" then
        local ok = pcall(emu.reset)
        response = ok and "RESET:ok" or "RESET:error"
        responseOk = ok
    elseif cmd == "REINIT" then
        local targets = arg1
        local mask = 0
        for token in tostring(targets):gmatch("[^,]+") do
            local key = token:lower():gsub("^%s+", ""):gsub("%s+$", "")
            if REINIT_TARGETS[key] then mask = mask | REINIT_TARGETS[key] end
        end
        if mask > 0 then
            local flags = read8(ADDR.reinitFlags)
            write8(ADDR.reinitFlags, (flags | mask) & 0xFF)
            local seq = (read8(ADDR.reinitSeq) + 1) & 0xFF
            write8(ADDR.reinitSeq, seq)
            response = string.format("REINIT:queued:mask=0x%02X,seq=%d", mask, seq)
        else
            responseOk = false
            response = "REINIT:error=invalid_targets"
        end
    elseif cmd == "REINIT_STATUS" then
        response = string.format('{"flags":%d,"status":%d,"error":%d,"seq":%d,"last":%d}',
            read8(ADDR.reinitFlags), read8(ADDR.reinitStatus), read8(ADDR.reinitError),
            read8(ADDR.reinitSeq), read8(ADDR.reinitLast))
    elseif cmd == "PRESERVE" then
        local action = (arg1 or ""):lower()
        if action == "status" or action == "" then
            local addrs = {}
            for _, a in ipairs(state.preserveList) do addrs[#addrs + 1] = string.format("0x%06X", a) end
            response = string.format("PRESERVE:enabled=%s,count=%d", state.preserveEnabled and "true" or "false", #state.preserveList)
        elseif action == "on" or action == "enable" then
            state.preserveEnabled = true
            response = "PRESERVE:enabled=true"
        elseif action == "off" or action == "disable" then
            state.preserveEnabled = false
            response = "PRESERVE:enabled=false"
        elseif action == "add" then
            local addr = parseAddr(arg2)
            if addr then
                local found = false
                for _, a in ipairs(state.preserveList) do if a == addr then found = true; break end end
                if not found then state.preserveList[#state.preserveList + 1] = addr end
                response = string.format("PRESERVE:added=0x%06X", addr)
            else
                responseOk = false
                response = "PRESERVE:error=invalid_addr"
            end
        elseif action == "remove" then
            local addr = parseAddr(arg2)
            if addr then
                local newList = {}
                for _, a in ipairs(state.preserveList) do if a ~= addr then newList[#newList + 1] = a end end
                state.preserveList = newList
                response = string.format("PRESERVE:removed=0x%06X", addr)
            else
                responseOk = false
                response = "PRESERVE:error=invalid_addr"
            end
        elseif action == "default" then
            state.preserveList = { 0x7EF357, 0x7EF34C, 0x7EF359, 0x7EF35A, 0x7EF354, 0x7EF355, 0x7EF356 }
            response = "PRESERVE:reset_to_default"
        else
            responseOk = false
            response = "PRESERVE:error=unknown_action"
        end
    elseif cmd == "OVERLAY" then
        local action = (arg1 or ""):lower()
        if action == "on" or action == "enable" then
            CONFIG.enableOverlay = true
            response = "OVERLAY:enabled"
        elseif action == "off" or action == "disable" then
            CONFIG.enableOverlay = false
            response = "OVERLAY:disabled"
        elseif action == "toggle" then
            CONFIG.enableOverlay = not CONFIG.enableOverlay
            response = "OVERLAY:" .. (CONFIG.enableOverlay and "enabled" or "disabled")
        else
            response = "OVERLAY:" .. (CONFIG.enableOverlay and "enabled" or "disabled")
        end
    elseif cmd == "CRASH" then
        -- Manual crash status check/clear
        local action = (arg1 or ""):lower()
        if action == "clear" then
            state.crashDetected = false
            state.crashReason = ""
            state.lastSignificantFrame = state.frameCount
            response = "CRASH:cleared"
        else
            response = string.format("CRASH:detected=%s,reason=%s,idle=%d",
                state.crashDetected and "true" or "false",
                state.crashReason ~= "" and state.crashReason or "none",
                state.frameCount - state.lastSignificantFrame)
        end
    elseif cmd == "DUMP" then
        -- Dump current state to log
        log("=== STATE DUMP ===")
        log(string.format("Module: $%02X:%02X, Room: $%02X, OW: $%02X",
            read8(ADDR.module), read8(ADDR.submodule), read8(ADDR.roomID), read8(ADDR.overworldArea)))
        log(string.format("Link: State=$%02X, Pos=(%d,%d)",
            read8(ADDR.linkState), read16(ADDR.linkPosX), read16(ADDR.linkPosY)))
        log(string.format("Idle: %d frames, Crash: %s",
            state.frameCount - state.lastSignificantFrame, state.crashDetected and "YES" or "no"))
        response = "DUMP:logged"
    elseif cmd == "DEBUG" or cmd == "LISTAPI" then
        local funcs = {}
        for k, v in pairs(emu) do if type(v) == "function" then funcs[#funcs + 1] = k end end
        table.sort(funcs)
        response = "EMU_FUNCTIONS:" .. table.concat(funcs, ",")
    else
        responseOk = false
        response = "ERR:unknown_command:" .. cmd
    end

    -- Write response
    if response ~= "" then
        local rf = io.open(RESPONSE_FILE, "w")
        if rf then
            if responseMode == "pipe" and reqId then
                rf:write(string.format("%s|%s|%s", reqId, responseOk and "OK" or "ERR", response))
            else
                rf:write(response)
            end
            rf:close()
        end
    end

    -- Clear command file
    local cf = io.open(CMD_FILE, "w")
    if cf then cf:write(""); cf:close() end
end

-- =============================================================================
-- Main Loop
-- =============================================================================

local function onExecHook()
    loadSavestateNow()
    saveSavestateNow()
end

function Main()
    state.frameCount = state.frameCount + 1

    applyInjectedInput()
    checkTransitions()
    checkCrashConditions()

    if state.frameCount % 10 == 0 then
        writeState()
    end

    processCommands()
    drawOverlay()
end

-- =============================================================================
-- Initialization
-- =============================================================================

os.execute("mkdir -p " .. BRIDGE_DIR)
os.execute("mkdir -p " .. LOG_DIR)

-- Initialize previous state
state.prev.module = read8(ADDR.module)
state.prev.submodule = read8(ADDR.submodule)
state.prev.roomID = read8(ADDR.roomID)
state.prev.overworldArea = read8(ADDR.overworldArea)
state.prev.indoors = read8(ADDR.indoors)
state.prev.linkState = read8(ADDR.linkState)
state.prev.linkPosX = read16(ADDR.linkPosX)
state.prev.linkPosY = read16(ADDR.linkPosY)
state.lastSignificantFrame = 0

-- Register callbacks
pcall(function()
    emu.addMemoryCallback(onExecHook, emu.callbackType.exec, 0x008051)
end)

emu.addEventCallback(Main, emu.eventType.endFrame)

-- Startup message
emu.displayMessage("Bridge", "OOS Unified Bridge Active")
log("=== OOS Unified Bridge Started ===")
log(string.format("Bridge dir: %s", BRIDGE_DIR))
log("Commands: STATE, READ, WRITE, PRESS, LOADSTATE, SAVESTATE, OVERLAY, CRASH, DUMP")
print("OOS Unified Bridge loaded. Send commands to: " .. CMD_FILE)
