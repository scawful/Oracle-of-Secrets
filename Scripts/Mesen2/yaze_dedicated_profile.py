"""Prepare settings for a *new* dedicated Yaze/Mesen profile.

This pure transformation is not connected to a launcher and writes no files.
Existing profiles require separate ownership and save-identity checks.
"""
from __future__ import annotations

import json
import math

_MAX_SETTINGS_BYTES = 16 * 1024 * 1024
_ISOLATED_PREFERENCES = {
    'OverrideSaveDataFolder': False,
    'SaveDataFolder': '',
    'OverrideSaveStateFolder': False,
    'SaveStateFolder': '',
}


def _unique_object(pairs):
    result = {}
    seen = set()
    for key, value in pairs:
        folded = key.casefold()
        if folded in seen:
            raise ValueError('Settings contain ambiguous duplicate keys')
        seen.add(folded)
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError('Invalid JSON constant: ' + value)


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Non-finite JSON number')
    return result


def _read_settings(raw):
    if type(raw) is not bytes or len(raw) > _MAX_SETTINGS_BYTES:
        raise ValueError('Settings must be bounded UTF-8 bytes')
    try:
        settings = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_unique_object,
                              parse_constant=_reject_constant, parse_float=_finite_float)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Cannot parse Mesen settings') from error
    if (type(settings) is not dict or type(settings.get('Input')) is not dict
            or type(settings.get('Preferences')) is not dict):
        raise ValueError('Mesen settings require Input and Preferences objects')
    return settings


def verify_existing_settings(raw):
    """Refuse an existing profile that redirects saves; never rewrite it."""
    preferences = _read_settings(raw)['Preferences']
    for name in ('OverrideSaveDataFolder', 'OverrideSaveStateFolder'):
        matches = [key for key in preferences if key.casefold() == name.casefold()]
        if matches and (matches[0] != name or preferences[matches[0]] is not False):
            raise ValueError('Existing Mesen profile redirects saves or is ambiguous')


def prepare_settings(raw):
    """Return isolated UTF-8 settings bytes without modifying the source.

    Only settings for a new, owned profile may use this transformation. The
    dedicated launch must independently prove its home and save directories.
    """
    settings = _read_settings(raw)
    preferences = settings['Preferences']
    protected = {name.casefold() for name in _ISOLATED_PREFERENCES}
    for key in list(preferences):
        if key.casefold() in protected:
            del preferences[key]
    preferences.update(_ISOLATED_PREFERENCES)
    return (json.dumps(settings, ensure_ascii=False, allow_nan=False, indent=2)
            + '\n').encode('utf-8')
