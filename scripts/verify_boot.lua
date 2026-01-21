-- Verify ROM Boot Script for Mesen
-- Uses Mesen Lua API to check if game reaches Title Screen state

local frameCount = 0
local bootSuccess = false
local TIMEOUT_FRAMES = 600 -- 10 seconds

function onTick()
  frameCount = frameCount + 1
  
  -- Check Game Mode (Address $7E0010 in ALTTP)
  -- 0x00 = Intro/Nintendo Logo, 0x01 = File Select, 0x02 = Copy, 0x03 = Erase, ...
  -- 0x07 = Dungeon, 0x09 = Overworld
  local gameMode = emu.read(0x7E0010, emu.memType.cpu)
  
  -- If we reached Intro or File Select, we booted!
  if gameMode > 0 then
    bootSuccess = true
    emu.log("SUCCESS: Booted to Game Mode " .. string.format("0x%02X", gameMode))
    emu.stop()
  end
  
  if frameCount > TIMEOUT_FRAMES then
    emu.log("FAILURE: Boot timeout. Stuck at Game Mode " .. string.format("0x%02X", gameMode))
    emu.stop()
  end
end

emu.addEventCallback(onTick, emu.eventType.endFrame)
