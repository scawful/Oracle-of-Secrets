-- Transition Debug Script for Mesen2
-- Traces screen transitions to find black screen bugs

local lastMode = -1
local lastSubmodule = -1
local lastINIDISP = -1
local logEnabled = true

-- Key addresses for transition state
local MODE      = 0x7E0010  -- Game module (6=UnderworldLoad, 7=Underworld, 9=Overworld)
local SUBMODULE = 0x7E0011  -- Submodule state within current module
local INIDISP_Q = 0x7E0013  -- INIDISP queue (screen brightness)
local FRAME     = 0x7E001A  -- Frame counter (main loop progress)
local MOSAIC    = 0x7E0094  -- Mosaic effect
local ENTRANCE  = 0x7E010E  -- Entrance ID
local ROOM      = 0x7E00A0  -- Current room ID

-- Module names for readable output
local MODULE_NAMES = {
    [0x00] = "Init",
    [0x05] = "UW_Opening",
    [0x06] = "UW_Load",       -- <-- This is where buildings are entered
    [0x07] = "Underworld",    -- <-- Dungeon gameplay
    [0x08] = "OW_Load",
    [0x09] = "Overworld",
    [0x0A] = "SpecialOW",
    [0x0B] = "OW_Transition",
    [0x0E] = "Interface",
    [0x0F] = "SpotlightClose",
    [0x10] = "SpotlightOpen",
    [0x11] = "FallingEntrance",
    [0x12] = "GameOver",
}

-- Module07 submodule names (dungeon state)
local SUBMODULE_07_NAMES = {
    [0x00] = "PlayerControl",
    [0x01] = "IntraroomTransition",  -- <-- Layer change (stairs)
    [0x02] = "InterroomTransition",  -- <-- Different room
    [0x03] = "OverlayChange",
    [0x04] = "UnlockDoor",
    [0x05] = "ControlShutters",
    [0x06] = "FatInterRoomStairs",   -- <-- Fat staircases
    [0x07] = "FallingTransition",
    [0x08] = "NorthIntraRoomStairs", -- <-- North-facing stairs
    [0x09] = "OpenCrackedDoor",
    [0x0A] = "ChangeBrightness",     -- <-- Screen fade
    [0x0B] = "DrainSwampPool",
}

local frameCount = 0
local transitionLog = {}

local function log(msg)
    if logEnabled then
        table.insert(transitionLog, string.format("[%d] %s", frameCount, msg))
        -- Keep only last 50 entries
        if #transitionLog > 50 then
            table.remove(transitionLog, 1)
        end
        emu.log(msg)
    end
end

local function getModuleName(mode)
    return MODULE_NAMES[mode] or string.format("Module%02X", mode)
end

local function getSubmoduleName(mode, sub)
    if mode == 0x07 then
        return SUBMODULE_07_NAMES[sub] or string.format("Sub%02X", sub)
    end
    return string.format("Sub%02X", sub)
end

function Main()
    frameCount = frameCount + 1

    local mode = emu.read(MODE, emu.memType.snesMemory)
    local submodule = emu.read(SUBMODULE, emu.memType.snesMemory)
    local inidispQ = emu.read(INIDISP_Q, emu.memType.snesMemory)
    local frame = emu.read(FRAME, emu.memType.snesMemory)
    local entrance = emu.read(ENTRANCE, emu.memType.snesMemory)
    local room = emu.read(ROOM, emu.memType.snesMemory)

    -- Log mode/submodule changes
    if mode ~= lastMode or submodule ~= lastSubmodule then
        local modeName = getModuleName(mode)
        local subName = getSubmoduleName(mode, submodule)
        log(string.format("MODE CHANGE: %s (%02X) -> %s", modeName, mode, subName))
        log(string.format("  Entrance: %02X, Room: %02X", entrance, room))
        lastMode = mode
        lastSubmodule = submodule
    end

    -- Log INIDISPQ changes (screen brightness / forced blank queue)
    if inidispQ ~= lastINIDISP then
        log(string.format("INIDISPQ: %02X -> %02X", lastINIDISP, inidispQ))
        if (inidispQ & 0x80) ~= 0 or (inidispQ & 0x0F) == 0x00 then
            log("  WARNING: Screen likely blanked (queued)!")
        end
        lastINIDISP = inidispQ
    end

    -- Draw HUD overlay
    local y = 8
    emu.drawRectangle(2, 2, 180, 70, 0x80000000, true, 1)
    emu.drawString(4, y, string.format("Mode: %s (%02X)", getModuleName(mode), mode), 0xFFFFFF, 0, 1)
    y = y + 10
    emu.drawString(4, y, string.format("Sub:  %s (%02X)", getSubmoduleName(mode, submodule), submodule), 0xFFFFFF, 0, 1)
    y = y + 10
    emu.drawString(4, y, string.format("INIDISPQ: %02X  Frame: %02X", inidispQ, frame),
        ((inidispQ & 0x80) ~= 0 or (inidispQ & 0x0F) == 0x00) and 0xFF0000 or 0xFFFFFF, 0, 1)
    y = y + 10
    emu.drawString(4, y, string.format("Room: %02X  Entrance: %02X", room, entrance), 0xFFFFFF, 0, 1)
    y = y + 10

    -- Show last few log entries
    y = y + 5
    local startIdx = math.max(1, #transitionLog - 3)
    for i = startIdx, #transitionLog do
        local entry = transitionLog[i]
        if entry then
            -- Truncate long entries
            if #entry > 40 then entry = entry:sub(1, 40) .. "..." end
            local color = entry:find("WARNING") and 0xFF0000 or 0xCCCCCC
            emu.drawString(4, y, entry, color, 0, 1)
            y = y + 8
        end
    end
end

-- Register main draw callback
emu.addEventCallback(Main, emu.eventType.endFrame)
emu.log("Transition debug script loaded. Watch for MODE/INIDISPQ changes.")
