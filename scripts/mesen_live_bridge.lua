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

local function write8(addr, value)
    emu.write(addr, value & 0xFF, emu.memType.snesMemory)
end

local function write16(addr, value)
    write8(addr, value)
    write8(addr + 1, math.floor(value / 256))
end

local function readSRAM(offset)
    return read8(0x7EF300 + offset)
end

local function parseAddr(value)
    if value == nil then return nil end
    if type(value) == "number" then return value end
    local s = tostring(value):gsub("^%s+", ""):gsub("%s+$", "")
    if s:sub(1, 2) == "0x" or s:sub(1, 2) == "0X" then
        return tonumber(s:sub(3), 16)
    end
    return tonumber(s)
end

local function readBlock(addr, length)
    local bytes = {}
    for i = 0, length - 1 do
        bytes[#bytes + 1] = string.format("%02X", read8(addr + i))
    end
    return table.concat(bytes)
end

-- Frame counter (since emu.getState().ppu may not exist)
local frameCounter = 0

-- Input injection system
local injectedInput = {
    f4 = 0,  -- D-pad + Select/Start/B/Y
    f6 = 0,  -- AXLR
    frames = 0,  -- How many frames to hold
    active = false
}

-- Button name to bit mapping
local BUTTONS = {
    -- F4 register (D-pad, Select, Start, B, Y)
    UP = {reg = "f4", bit = 0x08},
    DOWN = {reg = "f4", bit = 0x04},
    LEFT = {reg = "f4", bit = 0x02},
    RIGHT = {reg = "f4", bit = 0x01},
    SELECT = {reg = "f4", bit = 0x20},
    START = {reg = "f4", bit = 0x10},
    B = {reg = "f4", bit = 0x80},
    Y = {reg = "f4", bit = 0x40},
    -- F6 register (AXLR)
    A = {reg = "f6", bit = 0x80},
    X = {reg = "f6", bit = 0x40},
    L = {reg = "f6", bit = 0x20},
    R = {reg = "f6", bit = 0x10},
}

-- Parse button string (e.g., "A", "A+B", "UP+A")
local function parseButtons(btnStr)
    local f4, f6 = 0, 0
    for btn in btnStr:upper():gmatch("[^+]+") do
        btn = btn:gsub("^%s+", ""):gsub("%s+$", "")
        local mapping = BUTTONS[btn]
        if mapping then
            if mapping.reg == "f4" then
                f4 = f4 | mapping.bit
            else
                f6 = f6 | mapping.bit
            end
        end
    end
    return f4, f6
end

-- Apply injected input (called each frame)
local function applyInjectedInput()
    if not injectedInput.active then return end

    if injectedInput.frames > 0 then
        -- Write to input registers
        if injectedInput.f4 ~= 0 then
            local current = read8(0x7E00F4)
            write8(0x7E00F4, current | injectedInput.f4)
        end
        if injectedInput.f6 ~= 0 then
            local current = read8(0x7E00F6)
            write8(0x7E00F6, current | injectedInput.f6)
            -- Also set held register for continuous buttons
            local held = read8(0x7E00F2)
            write8(0x7E00F2, held | injectedInput.f6)
        end
        injectedInput.frames = injectedInput.frames - 1
    else
        injectedInput.active = false
        injectedInput.f4 = 0
        injectedInput.f6 = 0
    end
end

-- Get comprehensive game state
local function getState()
    local s = {}

    -- Timestamp
    s.timestamp = os.time()
    s.frame = frameCounter

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
    local tmp = STATE_FILE .. ".tmp"
    local f = io.open(tmp, "w")
    if f then
        f:write(json)
        f:close()
        os.rename(tmp, STATE_FILE)
    end
end

-- Check for commands
local lastCmdTime = 0
local function checkCommands()
    local f = io.open(CMD_FILE, "r")
    if not f then return end

    local content = f:read("*all")
    f:close()

    content = content:gsub("^%s+", ""):gsub("%s+$", "")
    if content == "" then return end

    -- Parse command
    -- Legacy format: "CMD:arg1:arg2"
    -- Pipe format: "id|CMD|arg1|arg2"
    local parts = {}
    local response = ""
    local responseMode = "legacy"
    local reqId = nil

    if content:find("|", 1, true) then
        for part in content:gmatch("[^|]+") do
            table.insert(parts, part)
        end
        reqId = parts[1]
        responseMode = "pipe"
    else
        for part in content:gmatch("[^:]+") do
            table.insert(parts, part)
        end
    end

    local cmd = responseMode == "pipe" and parts[2] or parts[1]
    cmd = cmd or ""
    cmd = cmd:upper()

    if cmd == "READ" and (parts[2] or parts[3]) then
        local addr = parseAddr(responseMode == "pipe" and parts[3] or parts[2])
        if addr then
            local val = read8(addr)
            response = string.format("READ:0x%06X=0x%02X (%d)", addr, val, val)
        end
    elseif cmd == "READ16" and (parts[2] or parts[3]) then
        local addr = parseAddr(responseMode == "pipe" and parts[3] or parts[2])
        if addr then
            local val = read16(addr)
            response = string.format("READ16:0x%06X=0x%04X (%d)", addr, val, val)
        end
    elseif cmd == "READBLOCK" and (parts[2] or parts[3]) then
        local addr = parseAddr(responseMode == "pipe" and parts[3] or parts[2])
        local len = parseAddr(responseMode == "pipe" and parts[4] or parts[3])
        if addr and len and len > 0 then
            local hex = readBlock(addr, len)
            response = string.format("READBLOCK:0x%06X:%d:%s", addr, len, hex)
        end
    elseif cmd == "WRITE" and (parts[2] or parts[3]) then
        local addr = parseAddr(responseMode == "pipe" and parts[3] or parts[2])
        local val = parseAddr(responseMode == "pipe" and parts[4] or parts[3])
        if addr and val then
            write8(addr, val)
            response = string.format("WRITE:0x%06X=0x%02X", addr, val % 256)
        end
    elseif cmd == "WRITE16" and (parts[2] or parts[3]) then
        local addr = parseAddr(responseMode == "pipe" and parts[3] or parts[2])
        local val = parseAddr(responseMode == "pipe" and parts[4] or parts[3])
        if addr and val then
            write16(addr, val)
            response = string.format("WRITE16:0x%06X=0x%04X", addr, val % 65536)
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
    elseif cmd == "INPUT" or cmd == "PRESS" then
        -- Inject button press: INPUT|buttons|frames
        -- Example: INPUT|A|5 (press A for 5 frames)
        -- Example: INPUT|UP+A|10 (press Up+A for 10 frames)
        local buttons = responseMode == "pipe" and parts[3] or parts[2]
        local frames = parseAddr(responseMode == "pipe" and parts[4] or parts[3]) or 5
        if buttons then
            local f4, f6 = parseButtons(buttons)
            injectedInput.f4 = f4
            injectedInput.f6 = f6
            injectedInput.frames = frames
            injectedInput.active = true
            response = string.format("INPUT:buttons=%s,f4=0x%02X,f6=0x%02X,frames=%d",
                buttons, f4, f6, frames)
        else
            response = "INPUT:error=no_buttons_specified"
        end
    elseif cmd == "RELEASE" then
        -- Stop any injected input
        injectedInput.active = false
        injectedInput.f4 = 0
        injectedInput.f6 = 0
        injectedInput.frames = 0
        response = "RELEASE:ok"
    end

    -- Write response
    if response ~= "" then
        local rf = io.open(RESPONSE_FILE, "w")
        if rf then
            if responseMode == "pipe" and reqId ~= nil then
                rf:write(string.format("%s|OK|%s", reqId, response))
            else
                rf:write(response)
            end
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

function Main()
    frameCounter = frameCounter + 1

    -- Apply any injected input BEFORE game processes input
    applyInjectedInput()

    -- Write state every 10 frames (~6 times per second at 60fps)
    if frameCounter % 10 == 0 then
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
print("Commands: PING, STATE, READ, READ16, READBLOCK, WRITE, WRITE16, LRSWAP, INPUT, RELEASE")
print("Input examples: INPUT|A|5, INPUT|UP+A|10, INPUT|START|1")
