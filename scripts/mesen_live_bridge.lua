-- Live Bridge for Mesen2 <-> CLI Communication
-- Writes game state to a JSON file for external polling
-- Also watches for command file to receive input

local BRIDGE_DIR = os.getenv("HOME") .. "/Documents/Mesen2/bridge"
local STATE_FILE = BRIDGE_DIR .. "/state.json"
local CMD_FILE = BRIDGE_DIR .. "/command.txt"
local RESPONSE_FILE = BRIDGE_DIR .. "/response.txt"

-- Ensure bridge directory exists (Lua doesn't have mkdir, so we try to open)
local function ensureDir()
    os.execute("mkdir -p " .. BRIDGE_DIR)
end

local function read8(addr)
    return emu.read(addr, emu.memType.snesMemory)
end

local function read16(addr)
    return read8(addr) + (read8(addr + 1) * 256)
end

local function readSRAM(offset)
    return read8(0x7EF300 + offset)
end

-- Get comprehensive game state
local function getState()
    local s = {}

    -- Timestamp
    s.timestamp = os.time()
    s.frame = emu.getState().ppu.frameCount

    -- Game mode
    s.mode = read8(0x7E0010)
    s.submode = read8(0x7E0011)
    s.indoors = read8(0x7E001B)
    s.roomId = read8(0x7E00A0)

    -- Link state
    s.linkState = read8(0x7E005D)
    s.linkX = read16(0x7E0022)
    s.linkY = read16(0x7E0020)
    s.linkDir = read8(0x7E002F)

    -- Equipment (for L/R swap testing)
    s.equippedSlot = read8(0x7E0202)
    s.goldstarOrHookshot = read8(0x7E0739)
    s.hookshotSRAM = readSRAM(0x42)  -- $7EF342

    -- Input state
    s.inputF4 = read8(0x7E00F4)  -- D-pad + select/start
    s.inputF6 = read8(0x7E00F6)  -- New AXLR this frame
    s.inputF2 = read8(0x7E00F2)  -- Held AXLR

    -- Health
    s.health = read8(0x7EF36D)
    s.maxHealth = read8(0x7EF36C)

    -- Menu state
    s.menuState = read8(0x7E0200)
    s.menuCursor = read8(0x7E0202)

    return s
end

-- Format state as JSON
local function toJSON(s)
    local lines = {}
    table.insert(lines, "{")
    table.insert(lines, string.format('  "timestamp": %d,', s.timestamp))
    table.insert(lines, string.format('  "frame": %d,', s.frame))
    table.insert(lines, string.format('  "mode": %d,', s.mode))
    table.insert(lines, string.format('  "submode": %d,', s.submode))
    table.insert(lines, string.format('  "indoors": %s,', s.indoors == 1 and "true" or "false"))
    table.insert(lines, string.format('  "roomId": %d,', s.roomId))
    table.insert(lines, string.format('  "linkState": %d,', s.linkState))
    table.insert(lines, string.format('  "linkX": %d,', s.linkX))
    table.insert(lines, string.format('  "linkY": %d,', s.linkY))
    table.insert(lines, string.format('  "linkDir": %d,', s.linkDir))
    table.insert(lines, string.format('  "equippedSlot": %d,', s.equippedSlot))
    table.insert(lines, string.format('  "goldstarOrHookshot": %d,', s.goldstarOrHookshot))
    table.insert(lines, string.format('  "hookshotSRAM": %d,', s.hookshotSRAM))
    table.insert(lines, string.format('  "inputF4": %d,', s.inputF4))
    table.insert(lines, string.format('  "inputF6": %d,', s.inputF6))
    table.insert(lines, string.format('  "inputF2": %d,', s.inputF2))
    table.insert(lines, string.format('  "health": %d,', s.health))
    table.insert(lines, string.format('  "maxHealth": %d,', s.maxHealth))
    table.insert(lines, string.format('  "menuState": %d,', s.menuState))
    table.insert(lines, string.format('  "menuCursor": %d', s.menuCursor))
    table.insert(lines, "}")
    return table.concat(lines, "\n")
end

-- Write state to file
local function writeState()
    local state = getState()
    local json = toJSON(state)
    local f = io.open(STATE_FILE, "w")
    if f then
        f:write(json)
        f:close()
    end
end

-- Check for commands
local lastCmdTime = 0
local function checkCommands()
    local f = io.open(CMD_FILE, "r")
    if not f then return end

    local content = f:read("*all")
    f:close()

    if content == "" then return end

    -- Parse command (format: "CMD:arg1:arg2")
    local parts = {}
    for part in content:gmatch("[^:]+") do
        table.insert(parts, part)
    end

    local cmd = parts[1]
    local response = ""

    if cmd == "READ" and parts[2] then
        -- Read memory address
        local addr = tonumber(parts[2])
        if addr then
            local val = read8(addr)
            response = string.format("READ:0x%06X=0x%02X (%d)", addr, val, val)
        end
    elseif cmd == "READ16" and parts[2] then
        local addr = tonumber(parts[2])
        if addr then
            local val = read16(addr)
            response = string.format("READ16:0x%06X=0x%04X (%d)", addr, val, val)
        end
    elseif cmd == "STATE" then
        response = toJSON(getState())
    elseif cmd == "PING" then
        response = "PONG:" .. os.time()
    elseif cmd == "LRSWAP" then
        -- Report L/R swap test readiness
        local s = getState()
        local ready = s.hookshotSRAM >= 2 and s.equippedSlot == 3
        local active = s.goldstarOrHookshot == 2 and "Goldstar" or "Hookshot"
        response = string.format("LRSWAP:ready=%s,active=%s,slot=%d,sram=%d",
            ready and "true" or "false", active, s.equippedSlot, s.hookshotSRAM)
    end

    -- Write response
    if response ~= "" then
        local rf = io.open(RESPONSE_FILE, "w")
        if rf then
            rf:write(response)
            rf:close()
        end
    end

    -- Clear command file
    local cf = io.open(CMD_FILE, "w")
    if cf then
        cf:write("")
        cf:close()
    end
end

-- Frame counter for throttling
local frameCount = 0

function Main()
    frameCount = frameCount + 1

    -- Write state every 10 frames (~6 times per second at 60fps)
    if frameCount % 10 == 0 then
        writeState()
    end

    -- Check commands every frame
    checkCommands()
end

-- Initialize
ensureDir()
emu.addEventCallback(Main, emu.eventType.endFrame)
emu.displayMessage("Bridge", "Live bridge active: " .. BRIDGE_DIR)
print("Live bridge started. State file: " .. STATE_FILE)
print("Send commands to: " .. CMD_FILE)
print("Commands: PING, STATE, READ:addr, READ16:addr, LRSWAP")
