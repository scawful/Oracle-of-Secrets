-- Mesen2 Socket Bridge
-- Connects to a Python TCP server to enable real-time control by AI Agents.

local socket = require("socket")
local json = require("json") -- Mesen2 built-in

local HOST = "127.0.0.1"
local PORT = 5050
local client = nil
local lastConnectFrame = 0
local CONNECT_INTERVAL = 60
local MESEN2_DIR = os.getenv("MESEN2_DIR") or (os.getenv("HOME") .. "/Documents/Mesen2")

local SAVESTATE_EXEC_HOOK = 0x008051 -- MainGameLoop .do_frame

-- === State Globals ===
local savestateStatus = "idle"
local savestateError = ""
local savestatePending = nil
local savestateLastPath = ""
local savePendingPath = nil
local savePendingSlot = nil

-- === Memory Helpers ===
local function read8(addr) return emu.read(addr, emu.memType.snesMemory) end
local function read16(addr) return read8(addr) + (read8(addr + 1) * 256) end
local function write8(addr, val) emu.write(addr, val & 0xFF, emu.memType.snesMemory) end
local function write16(addr, val) write8(addr, val); write8(addr + 1, math.floor(val / 256)) end
local function readSRAM(offset) return read8(0x7EF300 + offset) end

-- Debug reinit flags (custom WRAM region)
local DBG_REINIT_FLAGS = 0x7E0746
local DBG_REINIT_STATUS = 0x7E0747
local DBG_REINIT_ERROR = 0x7E0748
local DBG_REINIT_SEQ = 0x7E0749
local DBG_REINIT_LAST = 0x7E074A

local REINIT_TARGETS = {
    dialog = 0x01,
    sprites = 0x02,
    overlays = 0x04,
    msgbank = 0x08,
    roomcache = 0x10,
}

local function parseAddr(val)
    if type(val) == "number" then return val end
    if type(val) == "string" then
        local s = val:gsub("^%s+", ""):gsub("%s+$", "")
        if s:sub(1, 2) == "0x" or s:sub(1, 2) == "0X" then
            return tonumber(s:sub(3), 16)
        end
        return tonumber(s)
    end
    return nil
end

local function parseReinitTargets(raw)
    if raw == nil then return nil, "missing_targets" end
    local mask = 0
    local unknown = nil
    for token in tostring(raw):gmatch("[^,]+") do
        local key = token:lower():gsub("^%s+", ""):gsub("%s+$", "")
        local bit = REINIT_TARGETS[key]
        if bit then
            mask = mask | bit
        else
            unknown = key
            break
        end
    end
    if unknown then
        return nil, "unknown_target:" .. unknown
    end
    if mask == 0 then
        return nil, "empty_mask"
    end
    return mask, nil
end

local function readBlock(addr, len)
    local bytes = {}
    for i = 0, len - 1 do
        bytes[#bytes + 1] = string.format("%02X", read8(addr + i))
    end
    return table.concat(bytes)
end

local function writeBlock(addr, hex)
    if not hex then return false, "missing_hex" end
    hex = tostring(hex):gsub("%s+", "")
    if #hex == 0 then return false, "empty_hex" end
    if (#hex % 2) ~= 0 then return false, "odd_length" end
    local count = 0
    for i = 1, #hex, 2 do
        local byte = tonumber(hex:sub(i, i + 1), 16)
        if byte == nil then
            return false, "bad_hex"
        end
        write8(addr + count, byte)
        count = count + 1
    end
    return true, count
end

-- === JSON Encode (minimal, table-safe) ===
local function encodeJSON(value, depth, maxItems)
    depth = depth or 2
    maxItems = maxItems or 64
    local t = type(value)
    if value == nil then return "null" end
    if t == "number" then return tostring(value) end
    if t == "boolean" then return value and "true" or "false" end
    if t == "string" then
        local escaped = value:gsub("\\", "\\\\"):gsub("\"", "\\\""):gsub("\n", "\\n")
        return "\"" .. escaped .. "\""
    end
    if t ~= "table" then
        return "\"" .. tostring(value) .. "\""
    end
    if depth <= 0 then
        return "\"<table>\""
    end
    local isArray = (#value > 0)
    local out = {}
    if isArray then
        out[#out + 1] = "["
        local count = 0
        for i, v in ipairs(value) do
            out[#out + 1] = encodeJSON(v, depth - 1, maxItems)
            count = count + 1
            if i < #value and count < maxItems then
                out[#out + 1] = ","
            end
            if count >= maxItems then
                break
            end
        end
        out[#out + 1] = "]"
        return table.concat(out, "")
    end
    out[#out + 1] = "{"
    local count = 0
    for k, v in pairs(value) do
        count = count + 1
        if count > maxItems then
            break
        end
        out[#out + 1] = encodeJSON(tostring(k), 0)
        out[#out + 1] = ":"
        out[#out + 1] = encodeJSON(v, depth - 1, maxItems)
        out[#out + 1] = ","
    end
    if out[#out] == "," then
        out[#out] = nil
    end
    out[#out + 1] = "}"
    return table.concat(out, "")
end

local function sendJSON(payload)
    if not client then return false end
    local ok, encoded = pcall(encodeJSON, payload, 3, 128)
    if not ok then
        emu.log("encodeJSON failed: " .. tostring(encoded))
        return false
    end
    local okSend, err = pcall(function()
        client:send(encoded .. "\n")
    end)
    if not okSend then
        emu.log("send failed: " .. tostring(err))
        client = nil
        return false
    end
    return true
end

local function connect()
    if client then return true end
    local c = socket.tcp()
    c:settimeout(0.2)
    local ok, err = c:connect(HOST, PORT)
    if not ok then
        return false
    end
    c:settimeout(0)
    pcall(function() c:setoption("tcp-nodelay", true) end)
    client = c
    emu.log("Socket Bridge connected")
    return true
end

-- === State Gathering ===
local function getCpuState()
    local s = emu.getState()
    if not s or not s.cpu then return nil end
    return {
        pc = s.cpu.pc,
        a = s.cpu.a,
        x = s.cpu.x,
        y = s.cpu.y,
        sp = s.cpu.sp,
        p = s.cpu.p,
        db = s.cpu.db,
        pb = s.cpu.pb
    }
end

local function getGameState()
    local s = {}
    s.frame = emu.frameCount()
    s.timestamp = os.time()
    s.mode = read8(0x7E0010)
    s.submode = read8(0x7E0011)
    s.indoors = (read8(0x7E001B) == 1)
    s.roomId = read8(0x7E00A0)
    s.overworldArea = read8(0x7E008A)

    s.linkX = read16(0x7E0022)
    s.linkY = read16(0x7E0020)
    s.linkDir = read8(0x7E002F)
    s.linkState = read8(0x7E005D)
    s.health = read8(0x7EF36D)
    s.maxHealth = read8(0x7EF36C)

    s.equippedSlot = read8(0x7E0202)
    s.goldstarOrHookshot = read8(0x7E0739)
    s.hookshotSRAM = readSRAM(0x42)

    s.inputF4 = read8(0x7E00F4)
    s.inputF6 = read8(0x7E00F6)
    s.inputF2 = read8(0x7E00F2)

    s.savestateStatus = savestateStatus
    s.savestatePending = savestatePending
    s.savestateError = savestateError
    s.savestateLastPath = savestateLastPath

    s.reinitFlags = read8(DBG_REINIT_FLAGS)
    s.reinitStatus = read8(DBG_REINIT_STATUS)
    s.reinitError = read8(DBG_REINIT_ERROR)
    s.reinitSeq = read8(DBG_REINIT_SEQ)
    s.reinitLast = read8(DBG_REINIT_LAST)

    s.cpu = getCpuState()

    return s
end

-- === Input Injection ===
local injectedInput = { active = false, f4 = 0, f6 = 0, frames = 0, override_active = false, player = 1 }
local BUTTON_MAP = {
    UP={0x08,0}, DOWN={0x04,0}, LEFT={0x02,0}, RIGHT={0x01,0},
    SELECT={0x20,0}, START={0x10,0}, B={0x80,0}, Y={0x40,0},
    A={0,0x80}, X={0,0x40}, L={0,0x20}, R={0,0x10}
}

local function parseButtons(btnStr)
    local f4, f6 = 0, 0
    for btn in btnStr:upper():gmatch("[^+]+") do
        local map = BUTTON_MAP[btn:gsub("%s+", "")]
        if map then f4 = f4 | map[1]; f6 = f6 | map[2] end
    end
    return f4, f6
end

local function clearInputOverrides()
    if injectedInput.override_active and emu.setInputOverrides then
        pcall(emu.setInputOverrides, 1, {})
        injectedInput.override_active = false
    end
end

local function applyInput()
    if not injectedInput.active then
        clearInputOverrides()
        return
    end

    if injectedInput.frames > 0 then
        if emu.setInputOverrides then
            local state = {}
            if injectedInput.f4 & 0x08 ~= 0 then state.Up = true end
            if injectedInput.f4 & 0x04 ~= 0 then state.Down = true end
            if injectedInput.f4 & 0x02 ~= 0 then state.Left = true end
            if injectedInput.f4 & 0x01 ~= 0 then state.Right = true end
            if injectedInput.f4 & 0x20 ~= 0 then state.Select = true end
            if injectedInput.f4 & 0x10 ~= 0 then state.Start = true end
            if injectedInput.f4 & 0x80 ~= 0 then state.B = true end
            if injectedInput.f4 & 0x40 ~= 0 then state.Y = true end

            if injectedInput.f6 & 0x80 ~= 0 then state.A = true end
            if injectedInput.f6 & 0x40 ~= 0 then state.X = true end
            if injectedInput.f6 & 0x20 ~= 0 then state.L = true end
            if injectedInput.f6 & 0x10 ~= 0 then state.R = true end

            local player = injectedInput.player or 1
            emu.setInputOverrides(player, state)
            injectedInput.override_active = true
        else
            if injectedInput.f4 ~= 0 then write8(0x7E00F4, read8(0x7E00F4) | injectedInput.f4) end
            if injectedInput.f6 ~= 0 then
                write8(0x7E00F6, read8(0x7E00F6) | injectedInput.f6)
                write8(0x7E00F2, read8(0x7E00F2) | injectedInput.f6)
            end
        end

        injectedInput.frames = injectedInput.frames - 1
        if injectedInput.frames <= 0 then
            injectedInput.active = false
            clearInputOverrides()
        end
    end
end

-- === Savestate Handling ===
local function queueSavestateLoad(path)
    if not path or path == "" then
        savestateStatus = "error"
        savestateError = "missing_path"
        return false
    end
    savestatePending = path
    savestateStatus = "pending"
    savestateError = ""
    savestateLastPath = path
    return true
end

local function loadSavestateNow()
    if not savestatePending then return end
    local path = savestatePending
    savestatePending = nil

    local f = io.open(path, "rb")
    if not f then
        savestateStatus = "error"
        savestateError = "state_not_found:" .. path
        return
    end
    local data = f:read("*all")
    f:close()

    local ok, result = pcall(emu.loadSavestate, data)
    if ok and result then
        savestateStatus = "ok"
        savestateError = ""
    else
        savestateStatus = "error"
        savestateError = ok and "load_failed" or tostring(result)
    end
end

local function savestateExecCallback()
    if savestatePending then
        loadSavestateNow()
    end

    if savePendingPath then
        local path = savePendingPath
        savePendingPath = nil
        savePendingSlot = nil

        local ok, data = pcall(emu.createSavestate)
        if ok and data and #data > 0 then
            local sf = io.open(path, "wb")
            if sf then
                sf:write(data)
                sf:close()
                savestateStatus = "saved"
                savestateLastPath = path
                savestateError = ""
            else
                savestateStatus = "error"
                savestateError = "write_failed"
            end
        else
            savestateStatus = "error"
            savestateError = "createSavestate_failed:" .. tostring(data)
        end
    end
end

-- === Emulator Control ===
local function pauseEmu()
    if type(emu.pause) == "function" then
        local ok, res = pcall(emu.pause)
        if ok then return true, "pause" end
        return false, tostring(res)
    end
    if type(emu.breakExecution) == "function" then
        local ok, res = pcall(emu.breakExecution)
        if ok then return true, "breakExecution" end
        return false, tostring(res)
    end
    if type(emu.setPaused) == "function" then
        local ok, res = pcall(emu.setPaused, true)
        if ok then return true, "setPaused" end
        return false, tostring(res)
    end
    if type(emu.pauseCore) == "function" then
        local ok, res = pcall(emu.pauseCore)
        if ok then return true, "pauseCore" end
        return false, tostring(res)
    end
    return false, "unsupported"
end

local function resumeEmu()
    if type(emu.resume) == "function" then
        local ok, res = pcall(emu.resume)
        if ok then return true, "resume" end
        return false, tostring(res)
    end
    if type(emu.setPaused) == "function" then
        local ok, res = pcall(emu.setPaused, false)
        if ok then return true, "setPaused" end
        return false, tostring(res)
    end
    if type(emu.unpause) == "function" then
        local ok, res = pcall(emu.unpause)
        if ok then return true, "unpause" end
        return false, tostring(res)
    end
    return false, "unsupported"
end

local function stepEmu(kind)
    local candidates = {}
    if kind == "over" then
        candidates = {"stepOver", "step_over", "stepover"}
    elseif kind == "out" then
        candidates = {"stepOut", "step_out", "stepout"}
    else
        candidates = {"step", "stepInto", "step_into", "stepinto"}
    end
    local lastErr = nil
    for _, name in ipairs(candidates) do
        local fn = emu[name]
        if type(fn) == "function" then
            local ok, res = pcall(fn)
            if ok then return true, name end
            ok, res = pcall(fn, 1)
            if ok then return true, name end
            lastErr = res
        end
    end
    return false, lastErr or "unsupported"
end

local function warpTo(kind, target, x, y)
    kind = (kind or ""):upper()
    if not target then return false, "missing_target" end

    if kind == "OW" or kind == "OVERWORLD" then
        write8(0x7E001B, 0x00)
        write8(0x7E008A, target)
        write8(0x7E00A0, 0x00)
        if x then write16(0x7E0022, x) end
        if y then write16(0x7E0020, y) end
        write8(0x7E0010, 0x08)
        write8(0x7E0011, 0x00)
        write8(0x7E005D, 0x00)
        return true, "overworld"
    elseif kind == "UW" or kind == "UNDERWORLD" then
        write8(0x7E001B, 0x01)
        write8(0x7E00A0, target)
        if x then write16(0x7E0022, x) end
        if y then write16(0x7E0020, y) end
        write8(0x7E0010, 0x06)
        write8(0x7E0011, 0x00)
        write8(0x7E005D, 0x00)
        return true, "underworld"
    end
    return false, "invalid_kind"
end

-- === Command Processing ===
local function respond(id, ok, payload, err)
    local resp = {type = "response", id = id, status = ok and "ok" or "error"}
    if payload ~= nil then resp.payload = payload end
    if not ok then resp.error = err or "error" end
    sendJSON(resp)
end

-- === Breakpoints ===
local breakpoints = {} -- {id -> {callback, type, addr, endAddr, desc}}
local nextBpId = 1

local function onBreakpointHit(addr, typeName, id)
    local msg = {
        type = "event",
        kind = "breakpoint",
        id = id,
        addr = addr,
        mode = typeName,
        timestamp = os.time()
    }
    sendJSON(msg)
    
    -- Try to pause execution (Mesen2 vs Mesen-S vs others)
    if emu.breakExecution then
        emu.breakExecution()
    elseif emu.pause then
        emu.pause()
    elseif emu.setPaused then
        emu.setPaused(true)
    end
    
    emu.log(string.format("Breakpoint %d hit at 0x%X (%s)", id, addr, typeName))
end

local function addBreakpoint(typeStr, addr, endAddr)
    local cbType
    local typeName
    local typeStrLower = typeStr:lower()
    
    if typeStrLower == "exec" or typeStrLower == "execute" then
        cbType = emu.callbackType.exec
        typeName = "exec"
    elseif typeStrLower == "read" then
        cbType = emu.callbackType.read
        typeName = "read"
    elseif typeStrLower == "write" then
        cbType = emu.callbackType.write
        typeName = "write"
    else
        return nil, "invalid_type"
    end
    
    local id = nextBpId
    nextBpId = nextBpId + 1
    
    -- Closure to capture ID and Type
    local cb = function(address, value)
        onBreakpointHit(address, typeName, id)
    end
    
    -- Register with emulator
    -- signature: callback, type, startAddr, endAddr
    emu.addMemoryCallback(cb, cbType, addr, endAddr or addr)
    
    breakpoints[id] = {
        callback = cb,
        type = cbType,
        addr = addr,
        endAddr = endAddr or addr,
        desc = string.format("%s:0x%X", typeName, addr)
    }
    
    return id
end

local function removeBreakpoint(id)
    local bp = breakpoints[id]
    if bp then
        emu.removeMemoryCallback(bp.callback, bp.type, bp.addr, bp.endAddr)
        breakpoints[id] = nil
        return true
    end
    return false
end

local function clearBreakpoints()
    for id, bp in pairs(breakpoints) do
        emu.removeMemoryCallback(bp.callback, bp.type, bp.addr, bp.endAddr)
    end
    breakpoints = {}
end

local function slotPath(slot)
    return MESEN2_DIR .. "/SaveStates/oos168x_" .. slot .. ".mss"
end

local function processCommand(cmd)
    local cmdType = tostring(cmd.type or ""):upper()
    local id = cmd.id
    local ok = true
    local payload = nil
    local err = nil

    if cmdType == "PING" then
        payload = "PONG:" .. os.time()

    elseif cmdType == "ADD_BREAK" then
        local typeStr = cmd.kind or "exec"
        local addr = parseAddr(cmd.addr)
        local endAddr = parseAddr(cmd.endAddr)
        if addr then
            local bpId, bpErr = addBreakpoint(typeStr, addr, endAddr)
            if bpId then
                payload = string.format("BREAKPOINT:added:%d:%s", bpId, typeStr)
            else
                ok = false
                err = bpErr
            end
        else
            ok = false
            err = "invalid_addr"
        end

    elseif cmdType == "DEL_BREAK" then
        local bpId = parseAddr(cmd.bpId)
        if bpId then
            if removeBreakpoint(bpId) then
                payload = "BREAKPOINT:removed:" .. bpId
            else
                ok = false
                err = "not_found"
            end
        else
            ok = false
            err = "invalid_id"
        end

    elseif cmdType == "LIST_BREAK" then
        local list = {}
        for bpId, bp in pairs(breakpoints) do
            list[#list + 1] = string.format("%d|%s", bpId, bp.desc)
        end
        payload = "BREAKPOINTS:" .. table.concat(list, ",")

    elseif cmdType == "CLEAR_BREAK" then
        clearBreakpoints()
        payload = "BREAKPOINTS:cleared"

    elseif cmdType == "STATE" then
        payload = getGameState()

    elseif cmdType == "READ" then
        local addr = parseAddr(cmd.addr)
        if addr then
            local val = read8(addr)
            payload = string.format("READ:0x%06X=0x%02X (%d)", addr, val, val)
        else
            ok = false
            err = "invalid_addr"
        end

    elseif cmdType == "READ16" then
        local addr = parseAddr(cmd.addr)
        if addr then
            local val = read16(addr)
            payload = string.format("READ16:0x%06X=0x%04X (%d)", addr, val, val)
        else
            ok = false
            err = "invalid_addr"
        end

    elseif cmdType == "READBLOCK" then
        local addr = parseAddr(cmd.addr)
        local len = parseAddr(cmd.len or cmd.length)
        if addr and len and len > 0 then
            local hex = readBlock(addr, len)
            payload = string.format("READBLOCK:0x%06X:%d:%s", addr, len, hex)
        else
            ok = false
            err = "invalid_args"
        end

    elseif cmdType == "WRITE" then
        local addr = parseAddr(cmd.addr)
        local val = parseAddr(cmd.value or cmd.val)
        if addr and val ~= nil then
            write8(addr, val)
            payload = string.format("WRITE:0x%06X=0x%02X", addr, val % 256)
        else
            ok = false
            err = "invalid_args"
        end

    elseif cmdType == "WRITE16" then
        local addr = parseAddr(cmd.addr)
        local val = parseAddr(cmd.value or cmd.val)
        if addr and val ~= nil then
            write16(addr, val)
            payload = string.format("WRITE16:0x%06X=0x%04X", addr, val % 65536)
        else
            ok = false
            err = "invalid_args"
        end

    elseif cmdType == "WRITEBLOCK" then
        local addr = parseAddr(cmd.addr)
        local hex = cmd.hex
        if addr and hex then
            local okWrite, count = writeBlock(addr, hex)
            if okWrite then
                payload = string.format("WRITEBLOCK:0x%06X:%d", addr, count)
            else
                ok = false
                err = "writeblock:" .. tostring(count)
            end
        else
            ok = false
            err = "invalid_args"
        end

    elseif cmdType == "PRESS" or cmdType == "INPUT" then
        local buttons = cmd.buttons
        local frames = parseAddr(cmd.frames) or 5
        if buttons then
            local player = parseAddr(cmd.player) or 1
            local f4, f6 = parseButtons(buttons)
            injectedInput.f4 = f4
            injectedInput.f6 = f6
            injectedInput.frames = frames
            injectedInput.active = true
            injectedInput.player = player
            payload = string.format("INPUT:buttons=%s,f4=0x%02X,f6=0x%02X,frames=%d",
                buttons, f4, f6, frames)
        else
            ok = false
            err = "no_buttons_specified"
        end

    elseif cmdType == "RELEASE" then
        injectedInput.active = false
        injectedInput.f4 = 0
        injectedInput.f6 = 0
        injectedInput.frames = 0
        clearInputOverrides()
        payload = "RELEASE:ok"

    elseif cmdType == "REINIT" then
        local targets = cmd.targets
        local mask, perr = parseReinitTargets(targets)
        if not mask then
            ok = false
            err = perr
        else
            local flags = read8(DBG_REINIT_FLAGS)
            write8(DBG_REINIT_FLAGS, (flags | mask) & 0xFF)
            local status = read8(DBG_REINIT_STATUS)
            write8(DBG_REINIT_STATUS, status & (~mask & 0xFF))
            local errMask = read8(DBG_REINIT_ERROR)
            write8(DBG_REINIT_ERROR, errMask & (~mask & 0xFF))
            local seq = read8(DBG_REINIT_SEQ)
            seq = (seq + 1) & 0xFF
            write8(DBG_REINIT_SEQ, seq)
            payload = string.format("REINIT:queued:mask=0x%02X,seq=%d", mask, seq)
        end

    elseif cmdType == "REINIT_STATUS" then
        payload = {
            flags = read8(DBG_REINIT_FLAGS),
            status = read8(DBG_REINIT_STATUS),
            error = read8(DBG_REINIT_ERROR),
            seq = read8(DBG_REINIT_SEQ),
            last = read8(DBG_REINIT_LAST),
        }

    elseif cmdType == "LOADSTATE" then
        local path = cmd.path
        local slot = parseAddr(cmd.slot)
        if slot and slot >= 1 and slot <= 10 then
            path = slotPath(slot)
        end
        if path and queueSavestateLoad(path) then
            payload = "LOADSTATE:queued:" .. path
        else
            ok = false
            err = savestateError ~= "" and savestateError or "missing_path_or_slot"
        end

    elseif cmdType == "SAVESTATE" then
        local path = cmd.path
        local slot = parseAddr(cmd.slot)
        if slot and slot >= 1 and slot <= 10 then
            savePendingSlot = slot
            savePendingPath = slotPath(slot)
            savestateStatus = "pending"
            savestateError = ""
            payload = string.format("SAVESTATE:queued,slot=%d,path=%s", slot, savePendingPath)
        elseif path and path ~= "" then
            savePendingSlot = 0
            savePendingPath = path
            savestateStatus = "pending"
            savestateError = ""
            payload = "SAVESTATE:queued,path=" .. path
        else
            ok = false
            err = "missing_path_or_slot"
        end

    elseif cmdType == "LOADSLOT" then
        local slot = parseAddr(cmd.slot)
        if slot and slot >= 1 and slot <= 10 then
            local loadPath = slotPath(slot)
            if queueSavestateLoad(loadPath) then
                payload = string.format("LOADSLOT:queued,slot=%d,path=%s", slot, loadPath)
            else
                ok = false
                err = "queue_failed"
            end
        else
            ok = false
            err = "invalid_slot"
        end

    elseif cmdType == "SCREENSHOT" then
        local path = cmd.path
        if not path or path == "" then
            path = MESEN2_DIR .. "/bridge/screenshot_" .. os.time() .. ".png"
        end
        local okShot, result = pcall(emu.takeScreenshot, path)
        if not okShot then
            okShot, result = pcall(emu.takeScreenshot)
        end
        if okShot then
            if type(result) == "string" and result ~= "" then
                payload = "SCREENSHOT:" .. result
            else
                payload = "SCREENSHOT:" .. path
            end
        else
            ok = false
            err = tostring(result)
        end

    elseif cmdType == "PAUSE" then
        local okPause, name_or_err = pauseEmu()
        if okPause then
            payload = "PAUSE:ok:" .. name_or_err
        else
            ok = false
            err = tostring(name_or_err)
        end

    elseif cmdType == "RESUME" then
        local okResume, name_or_err = resumeEmu()
        if okResume then
            payload = "RESUME:ok:" .. name_or_err
        else
            ok = false
            err = tostring(name_or_err)
        end

    elseif cmdType == "STEP" then
        local okStep, name_or_err = stepEmu()
        if okStep then
            payload = "STEP:ok:" .. name_or_err
        else
            ok = false
            err = tostring(name_or_err)
        end

    elseif cmdType == "STEPOVER" then
        local okStep, name_or_err = stepEmu("over")
        if okStep then
            payload = "STEPOVER:ok:" .. name_or_err
        else
            ok = false
            err = tostring(name_or_err)
        end

    elseif cmdType == "STEPOUT" then
        local okStep, name_or_err = stepEmu("out")
        if okStep then
            payload = "STEPOUT:ok:" .. name_or_err
        else
            ok = false
            err = tostring(name_or_err)
        end

    elseif cmdType == "CPU" then
        local cpu = getCpuState()
        if cpu then
            payload = string.format("CPU:pc=%s,pb=%s,sp=%s,a=%s,x=%s,y=%s,p=%s,db=%s",
                tostring(cpu.pc), tostring(cpu.pb), tostring(cpu.sp), tostring(cpu.a),
                tostring(cpu.x), tostring(cpu.y), tostring(cpu.p), tostring(cpu.db))
        else
            ok = false
            err = "cpu_unavailable"
        end

    elseif cmdType == "STACK" then
        local count = parseAddr(cmd.count) or 32
        local cpu = getCpuState()
        if cpu and cpu.sp then
            local sp = cpu.sp
            local bytes = {}
            for i = 1, count do
                local addr = 0x7E0000 + ((sp + i) & 0xFFFF)
                bytes[#bytes + 1] = string.format("%02X", read8(addr))
            end
            payload = string.format("STACK:sp=0x%04X:%s", sp, table.concat(bytes))
        else
            ok = false
            err = "stack_unavailable"
        end

    elseif cmdType == "RESET" then
        local okReset, res = pcall(emu.reset)
        if okReset then
            payload = "RESET:ok"
        else
            ok = false
            err = tostring(res)
        end

    elseif cmdType == "STOP" then
        local okStop, res = pcall(emu.stop)
        if okStop then
            payload = "STOP:ok"
        else
            ok = false
            err = tostring(res)
        end

    elseif cmdType == "WARP" then
        local kind = cmd.kind
        local target = parseAddr(cmd.target)
        local x = parseAddr(cmd.x)
        local y = parseAddr(cmd.y)
        local okWarp, reason = warpTo(kind, target, x, y)
        if okWarp then
            payload = "WARP:ok:" .. tostring(reason)
        else
            ok = false
            err = tostring(reason)
        end

    elseif cmdType == "DEBUG" or cmdType == "LISTAPI" then
        local funcs = {}
        for k, v in pairs(emu) do
            if type(v) == "function" then
                funcs[#funcs + 1] = k
            end
        end
        table.sort(funcs)
        payload = "EMU_FUNCTIONS:" .. table.concat(funcs, ",")

    else
        ok = false
        err = "unknown_command"
    end

    respond(id, ok, payload, err)
end

-- === Main Update ===
local function update()
    local frame = emu.frameCount()
    if not client then
        if frame - lastConnectFrame >= CONNECT_INTERVAL then
            lastConnectFrame = frame
            connect()
        end
        return
    end

    while true do
        local line, err = client:receive("*l")
        if not line then
            if err ~= "timeout" then
                emu.log("Disconnected: " .. tostring(err))
                client = nil
            end
            break
        end
        local status, decoded = pcall(json.parse, line)
        if status and decoded then
            local okCmd, cmdErr = pcall(processCommand, decoded)
            if not okCmd then
                emu.log("Command error: " .. tostring(cmdErr))
            end
        else
            emu.log("JSON Error: " .. tostring(line))
        end
    end

    if client and frame % 10 == 0 then
        sendJSON({type = "state", payload = getGameState()})
    end
end

-- === Init ===
emu.addEventCallback(update, emu.eventType.endFrame)
if emu.eventType.inputPolled then
    emu.addEventCallback(applyInput, emu.eventType.inputPolled)
else
    emu.addEventCallback(applyInput, emu.eventType.endFrame)
end
emu.addMemoryCallback(savestateExecCallback, emu.callbackType.exec, SAVESTATE_EXEC_HOOK)

emu.displayMessage("Bridge", "Socket Bridge Loaded")
emu.log("Socket Bridge initialized. Waiting for server...")
connect()
