-- Save State Inspector for Mesen2
-- Extracts game state metadata for save state cataloging
-- Usage: Load in Mesen2 via Debug > Script Window

local function read8(addr)
    return emu.read(addr, emu.memType.snesMemory)
end

local function read16(addr)
    return read8(addr) + (read8(addr + 1) * 256)
end

local function readSRAM(offset)
    return read8(0x7EF300 + offset)
end

-- Item names for display
local ITEM_NAMES = {
    [0x40] = "Bow",
    [0x41] = "Boomerang",
    [0x42] = "Hookshot",
    [0x43] = "Bombs",
    [0x44] = "Powder",
    [0x45] = "Fire Rod",
    [0x46] = "Ice Rod",
    [0x47] = "Zora Mask",
    [0x48] = "Bunny Hood",
    [0x49] = "Deku Mask",
    [0x4A] = "Lamp",
    [0x4B] = "Hammer",
    [0x4C] = "Ocarina",
    [0x4D] = "Feather",
    [0x4E] = "Book",
    [0x50] = "Somaria",
    [0x51] = "Fishing Rod",
    [0x52] = "Stone Mask",
    [0x53] = "Mirror",
    [0x58] = "Wolf Mask",
}

local LINK_STATES = {
    [0x00] = "Default",
    [0x01] = "Falling",
    [0x02] = "Recoil",
    [0x04] = "Swimming",
    [0x06] = "Dashing",
    [0x13] = "Hookshot",
    [0x14] = "Mirror",
    [0x17] = "Falling2",
}

local GAME_MODES = {
    [0x00] = "Triforce/Init",
    [0x01] = "Title",
    [0x05] = "Loading",
    [0x07] = "Dungeon",
    [0x09] = "Overworld",
    [0x0E] = "Menu",
    [0x14] = "Messaging",
}

local function getGameState()
    local state = {}

    -- Core game mode
    state.mode = read8(0x7E0010)
    state.modeName = GAME_MODES[state.mode] or string.format("Unknown($%02X)", state.mode)
    state.submode = read8(0x7E0011)
    state.indoors = read8(0x7E001B)

    -- Room/Location
    state.roomId = read8(0x7E00A0)
    state.overworldArea = read8(0x7E008A)

    -- Link state
    state.linkState = read8(0x7E005D)
    state.linkStateName = LINK_STATES[state.linkState] or string.format("$%02X", state.linkState)
    state.linkX = read16(0x7E0022)
    state.linkY = read16(0x7E0020)
    state.linkDir = read8(0x7E002F)

    -- Equipment
    state.equippedItem = read8(0x7E0202)
    state.goldstarOrHookshot = read8(0x7E0739)

    -- Key SRAM flags
    state.hookshot = readSRAM(0x42)  -- $7EF342
    state.hasHookshot = state.hookshot >= 1
    state.hasGoldstar = state.hookshot >= 2

    -- Progress indicators
    state.dungeonScrolls = readSRAM(0x98)  -- Dungeon completion bits
    state.sideQuestProg = readSRAM(0xD7)
    state.sideQuestProg2 = readSRAM(0xD8)

    -- Masks owned
    state.dekuMask = readSRAM(0x49) > 0
    state.zoraMask = readSRAM(0x47) > 0
    state.wolfMask = readSRAM(0x58) > 0
    state.bunnyHood = readSRAM(0x48) > 0

    -- Health
    state.health = read8(0x7EF36D)
    state.maxHealth = read8(0x7EF36C)

    return state
end

local function formatStateJSON(state)
    local lines = {}
    table.insert(lines, "{")
    table.insert(lines, string.format('  "mode": "%s",', state.modeName))
    table.insert(lines, string.format('  "submode": %d,', state.submode))
    table.insert(lines, string.format('  "indoors": %s,', state.indoors == 1 and "true" or "false"))
    table.insert(lines, string.format('  "roomId": "0x%02X",', state.roomId))
    table.insert(lines, string.format('  "linkState": "%s",', state.linkStateName))
    table.insert(lines, string.format('  "linkPos": [%d, %d],', state.linkX, state.linkY))
    table.insert(lines, string.format('  "equippedSlot": %d,', state.equippedItem))
    table.insert(lines, string.format('  "hasHookshot": %s,', state.hasHookshot and "true" or "false"))
    table.insert(lines, string.format('  "hasGoldstar": %s,', state.hasGoldstar and "true" or "false"))
    table.insert(lines, string.format('  "goldstarActive": %s,', state.goldstarOrHookshot == 2 and "true" or "false"))
    table.insert(lines, string.format('  "masks": {'))
    table.insert(lines, string.format('    "deku": %s,', state.dekuMask and "true" or "false"))
    table.insert(lines, string.format('    "zora": %s,', state.zoraMask and "true" or "false"))
    table.insert(lines, string.format('    "wolf": %s,', state.wolfMask and "true" or "false"))
    table.insert(lines, string.format('    "bunny": %s', state.bunnyHood and "true" or "false"))
    table.insert(lines, '  },')
    table.insert(lines, string.format('  "health": "%d/%d",', state.health, state.maxHealth))
    table.insert(lines, string.format('  "dungeonClears": "0x%02X",', state.dungeonScrolls))
    table.insert(lines, string.format('  "sideQuests": ["0x%02X", "0x%02X"]', state.sideQuestProg, state.sideQuestProg2))
    table.insert(lines, "}")
    return table.concat(lines, "\n")
end

local function displayOverlay()
    local state = getGameState()

    local x = 260
    local y = 10

    emu.drawRectangle(x-2, y-2, 220, 180, 0x000000, true)
    emu.drawRectangle(x-2, y-2, 220, 180, 0x00FF00, false)

    emu.drawString(x, y, "=== STATE INSPECTOR ===", 0x00FF00)
    y = y + 14

    emu.drawString(x, y, string.format("Mode: %s", state.modeName), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("Room: $%02X  Indoor: %s",
        state.roomId, state.indoors == 1 and "Y" or "N"), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("Link: %s @ (%d,%d)",
        state.linkStateName, state.linkX, state.linkY), 0xFFFFFF)
    y = y + 12

    -- Equipment section
    emu.drawString(x, y, "--- Equipment ---", 0xFFFF00)
    y = y + 10

    emu.drawString(x, y, string.format("Slot: %d  Hookshot: $%02X",
        state.equippedItem, state.hookshot), 0xFFFFFF)
    y = y + 10

    local gsText = state.goldstarOrHookshot == 2 and "GOLDSTAR" or "HOOKSHOT"
    local gsColor = state.goldstarOrHookshot == 2 and 0xFFD700 or 0x00FFFF
    emu.drawString(x, y, string.format("Active: %s", gsText), gsColor)
    y = y + 12

    -- L/R Swap Test Status
    emu.drawString(x, y, "--- L/R SWAP TEST ---", 0xFF00FF)
    y = y + 10

    local canTest = state.hasGoldstar and state.equippedItem == 3
    local testColor = canTest and 0x00FF00 or 0xFF0000
    local testText = canTest and "READY" or "NEED: Both items + slot 3"
    emu.drawString(x, y, testText, testColor)
    y = y + 12

    -- Masks
    emu.drawString(x, y, "--- Masks ---", 0xFFFF00)
    y = y + 10

    local masks = {}
    if state.dekuMask then table.insert(masks, "Deku") end
    if state.zoraMask then table.insert(masks, "Zora") end
    if state.wolfMask then table.insert(masks, "Wolf") end
    if state.bunnyHood then table.insert(masks, "Bunny") end

    local maskText = #masks > 0 and table.concat(masks, ", ") or "None"
    emu.drawString(x, y, maskText, 0xFFFFFF)
    y = y + 12

    -- Progress
    emu.drawString(x, y, "--- Progress ---", 0xFFFF00)
    y = y + 10

    emu.drawString(x, y, string.format("Health: %d/%d", state.health, state.maxHealth), 0xFF6666)
    y = y + 10

    emu.drawString(x, y, string.format("Dungeons: $%02X", state.dungeonScrolls), 0xFFFFFF)
end

-- Print state to console on demand (F5)
local function printState()
    local state = getGameState()
    print("=== SAVE STATE METADATA ===")
    print(formatStateJSON(state))
    print("===========================")
    emu.displayMessage("Inspector", "State printed to console")
end

-- Register callbacks
emu.addEventCallback(displayOverlay, emu.eventType.endFrame)

-- Register F5 hotkey for console dump
emu.registerMemoryCallback(printState, emu.callbackType.cpuRead, 0x4016)

emu.displayMessage("Script", "State Inspector Loaded - Overlay active")
print("State Inspector loaded. Press F5 in-game to dump state to console.")
