-- ============================================================================
-- Oracle of Secrets - Debug Bridge Extension
-- ============================================================================
-- Extended debugging capabilities for remote control of Mesen2 debug windows.
-- Loads alongside mesen_live_bridge.lua to add advanced debug commands.
--
-- New Commands:
--   REGISTERS     - Get CPU registers (A, X, Y, S, P, PC, D, DB)
--   DISASM        - Disassemble at address
--   CALLSTACK     - Get call stack
--   WATCH_ADD     - Add watch expression
--   WATCH_LIST    - List watch expressions
--   WATCH_CLEAR   - Clear watches
--   EXEC_LUA      - Execute Lua code
--   TRACE_START   - Start execution trace
--   TRACE_STOP    - Stop execution trace
--   TRACE_GET     - Get trace buffer
--   LABELS        - Get/search labels
--   MEMORY_SEARCH - Search memory for value
--   PROFILE       - Get profiling data
-- ============================================================================

local DEBUG_BRIDGE_VERSION = "1.0.0"

-- =============================================================================
-- Configuration
-- =============================================================================

local BRIDGE_DIR = os.getenv("MESEN_BRIDGE_DIR") or (os.getenv("HOME") .. "/Documents/Mesen2/bridge")
local DEBUG_CMD_FILE = BRIDGE_DIR .. "/debug_command.txt"
local DEBUG_RESPONSE_FILE = BRIDGE_DIR .. "/debug_response.txt"
local TRACE_FILE = BRIDGE_DIR .. "/trace.jsonl"

-- =============================================================================
-- State
-- =============================================================================

local debugState = {
    -- Watch expressions
    watches = {},
    watchResults = {},

    -- Execution trace
    traceActive = false,
    traceBuffer = {},
    traceBufferMax = 1000,
    traceStartFrame = 0,

    -- Profiling
    profileActive = false,
    profileData = {},

    -- Labels cache
    labelsCache = {},
    labelsCacheValid = false,

    -- Frame counter
    frameCount = 0,
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

local function parseAddr(value)
    if value == nil then return nil end
    if type(value) == "number" then return value end
    local s = tostring(value):gsub("^%s+", ""):gsub("%s+$", "")
    if s:sub(1, 1) == "$" then s = "0x" .. s:sub(2) end
    if s:sub(1, 2):lower() == "0x" then
        return tonumber(s:sub(3), 16)
    end
    return tonumber(s)
end

local function jsonEscape(s)
    if type(s) ~= "string" then return tostring(s) end
    return s:gsub('\\', '\\\\'):gsub('"', '\\"'):gsub('\n', '\\n'):gsub('\r', '\\r'):gsub('\t', '\\t')
end

local function toJSON(tbl)
    if type(tbl) ~= "table" then
        if type(tbl) == "string" then
            return '"' .. jsonEscape(tbl) .. '"'
        elseif type(tbl) == "boolean" then
            return tbl and "true" or "false"
        else
            return tostring(tbl)
        end
    end

    -- Check if array
    local isArray = true
    local maxIdx = 0
    for k, _ in pairs(tbl) do
        if type(k) ~= "number" or k < 1 or math.floor(k) ~= k then
            isArray = false
            break
        end
        if k > maxIdx then maxIdx = k end
    end

    if isArray and maxIdx == #tbl then
        local items = {}
        for i = 1, #tbl do
            items[i] = toJSON(tbl[i])
        end
        return "[" .. table.concat(items, ",") .. "]"
    else
        local items = {}
        for k, v in pairs(tbl) do
            table.insert(items, '"' .. jsonEscape(tostring(k)) .. '":' .. toJSON(v))
        end
        return "{" .. table.concat(items, ",") .. "}"
    end
end

-- =============================================================================
-- CPU Register Access
-- =============================================================================

local function getRegisters()
    local regs = {}

    -- Try to get each register safely
    local function tryGet(name)
        local ok, val = pcall(function() return emu.getRegister(name) end)
        return ok and val or nil
    end

    regs.A = tryGet("A")
    regs.X = tryGet("X")
    regs.Y = tryGet("Y")
    regs.S = tryGet("S") or tryGet("SP")
    regs.P = tryGet("P") or tryGet("PS")
    regs.PC = tryGet("PC")
    regs.D = tryGet("D") or tryGet("DP")
    regs.DB = tryGet("DB") or tryGet("DBR")
    regs.K = tryGet("K") or tryGet("PBR")

    -- Status flag breakdown
    if regs.P then
        regs.flags = {
            N = (regs.P & 0x80) ~= 0,  -- Negative
            V = (regs.P & 0x40) ~= 0,  -- Overflow
            M = (regs.P & 0x20) ~= 0,  -- Accumulator size (0=16bit, 1=8bit)
            X = (regs.P & 0x10) ~= 0,  -- Index size
            D = (regs.P & 0x08) ~= 0,  -- Decimal
            I = (regs.P & 0x04) ~= 0,  -- IRQ disable
            Z = (regs.P & 0x02) ~= 0,  -- Zero
            C = (regs.P & 0x01) ~= 0,  -- Carry
        }
    end

    return regs
end

-- =============================================================================
-- Disassembly
-- =============================================================================

local function disassemble(address, count)
    count = count or 10
    local lines = {}

    -- Try using Mesen's disassembly API if available
    local ok, result = pcall(function()
        return emu.disassemble(address, count)
    end)

    if ok and result then
        return result
    end

    -- Fallback: simple byte dump with opcode names
    local OPCODES = {
        [0x00] = "BRK", [0x01] = "ORA", [0x02] = "COP", [0x08] = "PHP",
        [0x09] = "ORA", [0x0A] = "ASL", [0x10] = "BPL", [0x18] = "CLC",
        [0x20] = "JSR", [0x22] = "JSL", [0x28] = "PLP", [0x29] = "AND",
        [0x2A] = "ROL", [0x30] = "BMI", [0x38] = "SEC", [0x40] = "RTI",
        [0x48] = "PHA", [0x4C] = "JMP", [0x60] = "RTS", [0x6B] = "RTL",
        [0x68] = "PLA", [0x78] = "SEI", [0x80] = "BRA", [0x85] = "STA",
        [0x8D] = "STA", [0x9C] = "STZ", [0xA0] = "LDY", [0xA2] = "LDX",
        [0xA5] = "LDA", [0xA9] = "LDA", [0xAD] = "LDA", [0xC2] = "REP",
        [0xC9] = "CMP", [0xD0] = "BNE", [0xE2] = "SEP", [0xE6] = "INC",
        [0xEA] = "NOP", [0xF0] = "BEQ", [0xFB] = "XCE",
    }

    local addr = address
    for i = 1, count do
        local byte = read8(addr)
        local opname = OPCODES[byte] or "???"
        local bytes = string.format("%02X", byte)

        -- Add 1-2 more bytes for operands (simplified)
        if byte == 0x20 or byte == 0x4C or byte == 0xAD or byte == 0x8D then
            -- 3-byte absolute
            bytes = bytes .. string.format(" %02X %02X", read8(addr + 1), read8(addr + 2))
            addr = addr + 3
        elseif byte == 0x22 or byte == 0x5C then
            -- 4-byte long
            bytes = bytes .. string.format(" %02X %02X %02X", read8(addr + 1), read8(addr + 2), read8(addr + 3))
            addr = addr + 4
        elseif byte == 0x85 or byte == 0xA5 or byte == 0xA9 or byte == 0xC9 or byte == 0xD0 or byte == 0xF0 or byte == 0x80 or byte == 0x10 or byte == 0x30 or byte == 0xC2 or byte == 0xE2 then
            -- 2-byte
            bytes = bytes .. string.format(" %02X", read8(addr + 1))
            addr = addr + 2
        else
            addr = addr + 1
        end

        table.insert(lines, {
            address = string.format("$%06X", address + (i - 1)),
            bytes = bytes,
            instruction = opname,
        })
    end

    return lines
end

-- =============================================================================
-- Watch Expressions
-- =============================================================================

local function addWatch(id, expression, format)
    debugState.watches[id] = {
        expression = expression,
        format = format or "hex",
        lastValue = nil,
    }
    return true
end

local function removeWatch(id)
    debugState.watches[id] = nil
    return true
end

local function clearWatches()
    debugState.watches = {}
    debugState.watchResults = {}
    return true
end

local function evaluateWatches()
    debugState.watchResults = {}
    for id, watch in pairs(debugState.watches) do
        local ok, result = pcall(function()
            -- Try as address first
            local addr = parseAddr(watch.expression)
            if addr then
                return read16(addr)
            end
            -- Try as register
            return emu.getRegister(watch.expression)
        end)

        if ok then
            local formatted
            if watch.format == "dec" then
                formatted = tostring(result)
            elseif watch.format == "bin" then
                local bits = {}
                for i = 15, 0, -1 do
                    bits[#bits + 1] = ((result >> i) & 1) == 1 and "1" or "0"
                end
                formatted = table.concat(bits)
            else
                formatted = string.format("$%04X", result)
            end

            debugState.watchResults[id] = {
                expression = watch.expression,
                value = result,
                formatted = formatted,
                changed = watch.lastValue ~= nil and watch.lastValue ~= result,
            }
            watch.lastValue = result
        else
            debugState.watchResults[id] = {
                expression = watch.expression,
                error = "evaluation failed",
            }
        end
    end
    return debugState.watchResults
end

-- =============================================================================
-- Execution Tracing
-- =============================================================================

local function startTrace()
    debugState.traceActive = true
    debugState.traceBuffer = {}
    debugState.traceStartFrame = debugState.frameCount
    return true
end

local function stopTrace()
    debugState.traceActive = false
    return #debugState.traceBuffer
end

local function getTrace()
    return debugState.traceBuffer
end

local function recordTraceEntry()
    if not debugState.traceActive then return end
    if #debugState.traceBuffer >= debugState.traceBufferMax then
        table.remove(debugState.traceBuffer, 1)
    end

    local regs = getRegisters()
    table.insert(debugState.traceBuffer, {
        frame = debugState.frameCount,
        pc = regs.PC,
        a = regs.A,
        x = regs.X,
        y = regs.Y,
        s = regs.S,
        p = regs.P,
    })
end

-- =============================================================================
-- Memory Search
-- =============================================================================

local function searchMemory(value, size, startAddr, endAddr)
    size = size or 1
    startAddr = startAddr or 0x7E0000
    endAddr = endAddr or 0x7FFFFF

    local results = {}
    local maxResults = 100

    if size == 1 then
        value = value & 0xFF
        for addr = startAddr, endAddr do
            if read8(addr) == value then
                table.insert(results, string.format("$%06X", addr))
                if #results >= maxResults then break end
            end
        end
    elseif size == 2 then
        value = value & 0xFFFF
        for addr = startAddr, endAddr - 1 do
            if read16(addr) == value then
                table.insert(results, string.format("$%06X", addr))
                if #results >= maxResults then break end
            end
        end
    end

    return results
end

-- =============================================================================
-- Lua Execution
-- =============================================================================

local function execLua(code)
    local fn, err = load(code, "remote", "t", {
        emu = emu,
        read8 = read8,
        read16 = read16,
        print = print,
        string = string,
        table = table,
        math = math,
        pairs = pairs,
        ipairs = ipairs,
        tostring = tostring,
        tonumber = tonumber,
    })

    if not fn then
        return { error = "parse error: " .. tostring(err) }
    end

    local ok, result = pcall(fn)
    if not ok then
        return { error = "runtime error: " .. tostring(result) }
    end

    return { result = result }
end

-- =============================================================================
-- Command Processing
-- =============================================================================

local function processDebugCommands()
    local f = io.open(DEBUG_CMD_FILE, "r")
    if not f then return end
    local content = f:read("*all")
    f:close()
    content = content:gsub("^%s+", ""):gsub("%s+$", "")
    if content == "" then return end

    -- Parse: "id|CMD|arg1|arg2..."
    local parts = {}
    for part in content:gmatch("[^|]+") do parts[#parts + 1] = part end

    local reqId = parts[1] or "0"
    local cmd = (parts[2] or ""):upper()
    local args = {}
    for i = 3, #parts do args[i - 2] = parts[i] end

    local response = ""
    local responseOk = true

    if cmd == "REGISTERS" then
        response = toJSON(getRegisters())

    elseif cmd == "DISASM" then
        local addr = parseAddr(args[1]) or 0x008000
        local count = tonumber(args[2]) or 10
        response = toJSON(disassemble(addr, count))

    elseif cmd == "WATCH_ADD" then
        local id = args[1] or "w1"
        local expr = args[2] or "$7E0010"
        local fmt = args[3] or "hex"
        addWatch(id, expr, fmt)
        response = toJSON({ added = id, expression = expr })

    elseif cmd == "WATCH_LIST" then
        evaluateWatches()
        response = toJSON(debugState.watchResults)

    elseif cmd == "WATCH_REMOVE" then
        removeWatch(args[1] or "w1")
        response = toJSON({ removed = args[1] })

    elseif cmd == "WATCH_CLEAR" then
        clearWatches()
        response = "WATCH_CLEAR:ok"

    elseif cmd == "TRACE_START" then
        startTrace()
        response = "TRACE_START:ok"

    elseif cmd == "TRACE_STOP" then
        local count = stopTrace()
        response = toJSON({ stopped = true, entries = count })

    elseif cmd == "TRACE_GET" then
        response = toJSON(getTrace())

    elseif cmd == "MEMORY_SEARCH" then
        local value = parseAddr(args[1]) or 0
        local size = tonumber(args[2]) or 1
        local startAddr = parseAddr(args[3])
        local endAddr = parseAddr(args[4])
        local results = searchMemory(value, size, startAddr, endAddr)
        response = toJSON({ count = #results, addresses = results })

    elseif cmd == "EXEC_LUA" then
        -- Decode base64 or use raw
        local code = args[1] or ""
        -- Simple base64 decode attempt
        local decoded = code
        local ok, result = pcall(function()
            local b = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
            decoded = code:gsub('.', function(x)
                if x == '=' then return '' end
                local r, f = '', (b:find(x) - 1)
                for i = 6, 1, -1 do r = r .. (f % 2^i - f % 2^(i-1) > 0 and '1' or '0') end
                return r
            end):gsub('%d%d%d?%d?%d?%d?%d?%d?', function(x)
                if #x ~= 8 then return '' end
                local c = 0
                for i = 1, 8 do c = c + (x:sub(i, i) == '1' and 2^(8-i) or 0) end
                return string.char(c)
            end)
            return decoded
        end)
        if not ok then decoded = code end

        local result = execLua(decoded)
        response = toJSON(result)

    elseif cmd == "VERSION" then
        response = toJSON({ version = DEBUG_BRIDGE_VERSION, commands = {
            "REGISTERS", "DISASM", "WATCH_ADD", "WATCH_LIST", "WATCH_REMOVE",
            "WATCH_CLEAR", "TRACE_START", "TRACE_STOP", "TRACE_GET",
            "MEMORY_SEARCH", "EXEC_LUA", "VERSION"
        }})

    else
        responseOk = false
        response = "ERR:unknown_debug_command:" .. cmd
    end

    -- Write response
    local rf = io.open(DEBUG_RESPONSE_FILE, "w")
    if rf then
        rf:write(string.format("%s|%s|%s", reqId, responseOk and "OK" or "ERR", response))
        rf:close()
    end

    -- Clear command file
    local cf = io.open(DEBUG_CMD_FILE, "w")
    if cf then cf:write(""); cf:close() end
end

-- =============================================================================
-- Main Loop Hook
-- =============================================================================

local function debugBridgeFrame()
    debugState.frameCount = debugState.frameCount + 1

    -- Record trace if active
    recordTraceEntry()

    -- Process debug commands every frame
    processDebugCommands()

    -- Evaluate watches every 10 frames
    if debugState.frameCount % 10 == 0 then
        evaluateWatches()
    end
end

-- =============================================================================
-- Initialization
-- =============================================================================

os.execute("mkdir -p " .. BRIDGE_DIR)

emu.addEventCallback(debugBridgeFrame, emu.eventType.endFrame)

emu.displayMessage("Debug Bridge", "v" .. DEBUG_BRIDGE_VERSION .. " loaded")
print("OOS Debug Bridge v" .. DEBUG_BRIDGE_VERSION .. " loaded")
print("Debug commands: " .. DEBUG_CMD_FILE)
