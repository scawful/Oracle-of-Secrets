-- Water/Collision Debug Script for Mesen2
-- Shows Link's position, state, and collision info

local overlayVisible = true

local DIR_ADDR = 0x7E002F
local DIR_NAMES = {
    [0x00] = "Up",
    [0x02] = "Down",
    [0x04] = "Left",
    [0x06] = "Right",
}

-- Offsets used by TileDetect_MainHandler for deep water checks
-- (direction-based pixel offsets applied before collision lookup)
local DIR_OFFSETS = {
    [0x00] = { x = 8,  y = 20 }, -- Up
    [0x02] = { x = 8,  y = 20 }, -- Down
    [0x04] = { x = 0,  y = 23 }, -- Left
    [0x06] = { x = 15, y = 23 }, -- Right
}

local function getCollisionOffset(x, y)
    -- Room-local coordinates (room is 512x512 pixels = 64x64 tiles)
    local localX = x % 512
    local localY = y % 512
    local x_tile = math.floor(localX / 8)
    local y_tile = math.floor(localY / 8)
    return (y_tile * 64) + x_tile, x_tile, y_tile, localX, localY
end

local function getAdjustedCollisionOffset(x, y, dir)
    local offset = DIR_OFFSETS[dir] or DIR_OFFSETS[0x00]
    local adjX = x + offset.x
    local adjY = y + offset.y
    local adjOffset, adjTileX, adjTileY, adjLocalX, adjLocalY = getCollisionOffset(adjX, adjY)
    return adjOffset, adjTileX, adjTileY, adjLocalX, adjLocalY, adjX, adjY, offset.x, offset.y
end

function Main()
    -- Skip drawing if overlay disabled
    if not overlayVisible then return end

    -- Link Position (world coordinates)
    local linkX = emu.read(0x7E0022, emu.memType.snesMemory) + (emu.read(0x7E0023, emu.memType.snesMemory) * 256)
    local linkY = emu.read(0x7E0020, emu.memType.snesMemory) + (emu.read(0x7E0021, emu.memType.snesMemory) * 256)

    -- Link State
    local linkState = emu.read(0x7E005D, emu.memType.snesMemory)
    local animStep = emu.read(0x7E002E, emu.memType.snesMemory)
    local submodule = emu.read(0x7E001C, emu.memType.snesMemory)
    local action = emu.read(0x7E0024, emu.memType.snesMemory)
    local speed = emu.read(0x7E0050, emu.memType.snesMemory)

    -- Water flags
    local doorFlag = emu.read(0x7E0403, emu.memType.snesMemory)
    local deepWater = emu.read(0x7E0345, emu.memType.snesMemory)

    -- Room info
    local roomID = emu.read(0x7E00A0, emu.memType.snesMemory)

    -- Calculate collision offset and read value (room-local)
    local collOffset, tileX, tileY, localX, localY = getCollisionOffset(linkX, linkY)
    local collValue = emu.read(0x7F2000 + collOffset, emu.memType.snesMemory)
    local collValueB = emu.read(0x7F3000 + collOffset, emu.memType.snesMemory)

    -- Adjusted collision lookup (matches engine behavior)
    local dir = emu.read(DIR_ADDR, emu.memType.snesMemory)
    local dirName = DIR_NAMES[dir] or string.format("$%02X", dir)
    local adjOffset, adjTileX, adjTileY, adjLocalX, adjLocalY, adjX, adjY, offX, offY =
        getAdjustedCollisionOffset(linkX, linkY, dir)
    local adjCollValue = emu.read(0x7F2000 + adjOffset, emu.memType.snesMemory)
    local adjCollValueB = emu.read(0x7F3000 + adjOffset, emu.memType.snesMemory)

    -- Display on screen (right side, outside game area)
    -- SNES is 256x224, place overlay at x=260 to be outside main view
    local y = 10
    local x = 260

    emu.drawRectangle(x-2, y-2, 220, 190, 0x000000, true)
    emu.drawRectangle(x-2, y-2, 220, 190, 0xFFFFFF, false)

    emu.drawString(x, y, "=== WATER DEBUG ===", 0x00FFFF)
    y = y + 12

    emu.drawString(x, y, string.format("Room: $%02X", roomID), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("World Pos: (%d, %d)", linkX, linkY), 0x888888)
    y = y + 10

    emu.drawString(x, y, string.format("Local Pos: (%d, %d)", localX, localY), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("Dir: %s ($%02X)", dirName, dir), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("Tile Pos: (%d, %d)", tileX, tileY), 0xFFFF00)
    y = y + 10

    emu.drawString(x, y, string.format("Coll Offset: $%04X", collOffset), 0xFFFF00)
    y = y + 10

    emu.drawString(x, y, string.format("Adj Pos: (%d, %d) (+%d,+%d)", adjX, adjY, offX, offY), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("Adj Tile: (%d, %d)", adjTileX, adjTileY), 0xFFFF00)
    y = y + 10

    emu.drawString(x, y, string.format("Adj Offset: $%04X", adjOffset), 0xFFFF00)
    y = y + 10

    -- Color code collision value (adjusted)
    local collColor = 0xFFFFFF
    if adjCollValue == 0x08 then
        collColor = 0x00FF00  -- Green = deep water (good)
    elseif adjCollValue == 0x09 then
        collColor = 0x00FFFF  -- Cyan = shallow water
    elseif adjCollValue == 0x00 then
        collColor = 0xFF0000  -- Red = floor (bad for swim)
    end

    emu.drawString(x, y, string.format("Raw A:%02X B:%02X  Adj A:%02X B:%02X",
        collValue, collValueB, adjCollValue, adjCollValueB), collColor)
    y = y + 12

    emu.drawString(x, y, string.format("LinkState $5D: $%02X", linkState), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("AnimStep $2E: $%02X", animStep), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("Submod $1C: $%02X", submodule), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("Action $24: $%02X", action), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("Speed $50: $%02X", speed), 0xFFFFFF)
    y = y + 12

    emu.drawString(x, y, string.format("Door $0403: $%02X", doorFlag), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("DeepWater $0345: $%02X", deepWater), 0xFFFFFF)

    -- Collision legend
    y = y + 12
    emu.drawString(x, y, "$08=DeepWater $09=Shallow $00=Floor", 0x888888)
end

emu.addEventCallback(Main, emu.eventType.endFrame)
emu.displayMessage("Script", "Water Debug Loaded")
