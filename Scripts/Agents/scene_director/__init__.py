"""Scene director: drive Link inside one room from a scene file.

Modules:
  pathfind   A* over the live underworld collision map (offline, no emulator).
  scenefile  JSON scene loader and the RAM expression evaluator (offline).
  runner     Private Mesen session that executes a scene (needs Mesen2 OOS).
"""
