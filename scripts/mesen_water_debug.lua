-- Water/Collision Debug Script for Mesen2
-- Shows Link's position, state, and collision info

local overlayVisible = true

function getCollisionOffset(x, y)
    -- Room-local coordinates (room is 512x512 pixels = 64x64 tiles)
    local localX = x % 512
    local localY = y % 512
    local x_tile = math.floor(localX / 8)
    local y_tile = math.floor(localY / 8)
    return (y_tile * 64) + x_tile, x_tile, y_tile, localX, localY
end

function Main()
    -- Skip drawing if overlay disabled
    if not overlayVisible then return end

    -- Link Position (world coordinates)
    local linkX = emu.read(0x7E0022, emu.memType.snesMemory) + (emu.read(0x7E0023, emu.memType.snesMemory) * 256)
    local linkY = emu.read(0x7E0020, emu.memType.snesMemory) + (emu.read(0x7E0021, emu.memType.snesMemory) * 256)

    -- Link State
    local linkState = emu.read(0x7E002E, emu.memType.snesMemory)
    local submodule = emu.read(0x7E001C, emu.memType.snesMemory)
    local action = emu.read(0x7E0024, emu.memType.snesMemory)
    local speed = emu.read(0x7E0050, emu.memType.snesMemory)

    -- Water flags
    local doorFlag = emu.read(0x7E0403, emu.memType.snesMemory)
    local deepWater = emu.read(0x7E005D, emu.memType.snesMemory)

    -- Room info
    local roomID = emu.read(0x7E00A0, emu.memType.snesMemory)

    -- Calculate collision offset and read value (room-local)
    local collOffset, tileX, tileY, localX, localY = getCollisionOffset(linkX, linkY)
    local collValue = emu.read(0x7F2000 + collOffset, emu.memType.snesMemory)
    local collValueB = emu.read(0x7F3000 + collOffset, emu.memType.snesMemory)

    -- Display on screen (right side, outside game area)
    -- SNES is 256x224, place overlay at x=260 to be outside main view
    local y = 10
    local x = 260

    emu.drawRectangle(x-2, y-2, 200, 145, 0x000000, true)
    emu.drawRectangle(x-2, y-2, 200, 145, 0xFFFFFF, false)

    emu.drawString(x, y, "=== WATER DEBUG ===", 0x00FFFF)
    y = y + 12

    emu.drawString(x, y, string.format("Room: $%02X", roomID), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("World Pos: (%d, %d)", linkX, linkY), 0x888888)
    y = y + 10

    emu.drawString(x, y, string.format("Local Pos: (%d, %d)", localX, localY), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("Tile Pos: (%d, %d)", tileX, tileY), 0xFFFF00)
    y = y + 10

    emu.drawString(x, y, string.format("Coll Offset: $%04X", collOffset), 0xFFFF00)
    y = y + 10

    -- Color code collision value
    local collColor = 0xFFFFFF
    if collValue == 0x08 then
        collColor = 0x00FF00  -- Green = deep water (good)
    elseif collValue == 0x09 then
        collColor = 0x00FFFF  -- Cyan = shallow water
    elseif collValue == 0x00 then
        collColor = 0xFF0000  -- Red = floor (bad for swim)
    end

    emu.drawString(x, y, string.format("COLMAPA: $%02X  COLMAPB: $%02X", collValue, collValueB), collColor)
    y = y + 12

    emu.drawString(x, y, string.format("State $2E: $%02X", linkState), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("Submod $1C: $%02X", submodule), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("Action $24: $%02X", action), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("Speed $50: $%02X", speed), 0xFFFFFF)
    y = y + 12

    emu.drawString(x, y, string.format("Door $0403: $%02X", doorFlag), 0xFFFFFF)
    y = y + 10

    emu.drawString(x, y, string.format("DeepWater $5D: $%02X", deepWater), 0xFFFFFF)

    -- Collision legend
    y = y + 12
    emu.drawString(x, y, "$08=DeepWater $09=Shallow $00=Floor", 0x888888)
end

emu.addEventCallback(Main, emu.eventType.endFrame)
emu.displayMessage("Script", "Water Debug Loaded")
