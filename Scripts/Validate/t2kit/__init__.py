"""Shared native T2 kit: headless Mesen2 sessions for Oracle scenarios.

A scenario is a short module with FIXTURE, CASES and run(t, case); run_t2.py
builds the refs, takes the heavy lock and runs it. See README.md.
"""
from .dungeon import DungeonTiles, rect, room_origin
from .fixtures import Fixture, load_fixture, load_registry
from .session import ScenarioError, Session

__all__ = ['DungeonTiles', 'Fixture', 'ScenarioError', 'Session', 'load_fixture', 'load_registry',
           'rect', 'room_origin']
