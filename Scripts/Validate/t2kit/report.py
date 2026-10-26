"""Candidate vs control verdicts and the result table."""
from __future__ import annotations


def outcome(result: dict | None) -> str:
    """PASS, FAIL (n checks), ERROR, or '-' for a run that did not happen."""
    if result is None:
        return '-'
    if result.get('state') == 'error':
        return 'ERROR'
    failed = [c for c in result.get('checks', []) if not c.get('matches_expectation')]
    if result.get('passed') and not failed:
        return 'PASS'
    return f'FAIL ({len(failed)})' if failed else 'FAIL'


def verdict(candidate: dict | None, control: dict | None) -> str:
    cand, ctrl = outcome(candidate) == 'PASS', outcome(control) == 'PASS'
    if candidate is None:
        return 'not run'
    if control is None:
        return 'pass' if cand else 'FAIL'
    if cand and ctrl:
        return 'pass (control also passes)'
    if cand:
        return 'pass (control fails)'
    if ctrl:
        return 'REGRESSION (control passes)'
    return 'FAIL (control also fails)'


def table(rows: list[dict]) -> str:
    """Markdown table from rows {case, candidate: result|None, control: result|None}."""
    lines = ['| case | candidate | control | verdict |', '|---|---|---|---|']
    for row in rows:
        lines.append(f"| {row['case']} | {outcome(row.get('candidate'))} | {outcome(row.get('control'))} | "
                     f"{verdict(row.get('candidate'), row.get('control'))} |")
    return '\n'.join(lines)


def failed_checks(result: dict | None) -> list[str]:
    if not result:
        return []
    names = [c['name'] for c in result.get('checks', []) if not c.get('matches_expectation')]
    if result.get('error'):
        names.append(result['error'])
    return names
