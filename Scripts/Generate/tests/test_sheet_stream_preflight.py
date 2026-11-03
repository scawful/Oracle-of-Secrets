"""Consumed extents, aliases and rejection guards for the bank $23 preflight."""
import importlib.util
import argparse
import contextlib
import hashlib
import io
import json
import tempfile
from unittest import mock
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sheet_table as sheets
import lz2


class StreamPreflight(unittest.TestCase):
    def fixture(self, candidate=False):
        rom=bytearray(0x200000)
        rom[0x10000:0x10007]=bytes.fromhex('e7ff00e5ff00ff')
        two=lz2.stored(bytes(0x800)); rom[0x30000:0x30000+len(two)]=two
        tables=(sheets.NEW_BANK,sheets.NEW_HIGH,sheets.NEW_LOW) if candidate else (sheets.TBL_BANK,sheets.TBL_HIGH,sheets.TBL_LOW)
        for g in range(256 if candidate else 223):
            ptr=0x848000 if 0x73<=g<=0x7e else 0x868000 if g in (0x71,0x72,0xda,0xdb,0xdc,0xdd,0xde) else 0x828000
            if candidate and g>=0xdf: ptr=0x23fc75
            for t,shift in zip(tables,(16,8,0)): rom[sheets.pc(t)+g]=(ptr>>shift)&255
        if candidate: rom[0x11fc75:0x11fc7c]=bytes.fromhex('e7ff00e5ff00ff')
        return rom

    def point(self,rom,g,pointer):
        for t,shift in zip((sheets.TBL_BANK,sheets.TBL_HIGH,sheets.TBL_LOW),(16,8,0)):
            rom[sheets.pc(t)+g]=(pointer>>shift)&255

    def test_compressed_crossing_and_aliases(self):
        rom=self.fixture(); rom[0x11fbff:0x11fc06]=bytes.fromhex('e7ff00e5ff00ff')
        for g in (0,1): self.point(rom,g,0x23fbff)
        result=sheets.stream_extents(rom,'base')
        self.assertFalse(result['errors'])
        self.assertEqual(result['rows'][0]['end_pc'],0x11fc06)
        self.assertIn([0,1],[x['ids'] for x in result['aliases']])

    def test_raw_crossing(self):
        rom=self.fixture(); self.point(rom,0x73,0x23fb00)
        row=next(r for r in sheets.stream_extents(rom,'base')['rows'] if r['id']==0x73)
        self.assertEqual(row['end_pc'],0x120100)

    def test_invalid_pointer_and_decoder_error_are_retained(self):
        rom=self.fixture(); self.point(rom,0,0x230001); self.point(rom,1,0xBFFFFF)
        errors=sheets.stream_extents(rom,'base')['errors']
        self.assertEqual({x['id'] for x in errors},{0,1})

    def symbols(self):
        return '\n'.join(['23:FC00 GfxSheet_Helpers','23:FD00 GfxSheet_Bank',
                          '23:FE00 GfxSheet_High','23:FF00 GfxSheet_Low','23:FC75 GfxSheet_EmptyStream'])

    def test_only_intended_new_rows_allowed(self):
        base=self.fixture(); candidate=self.fixture(True)
        self.assertEqual(sheets.ownership_preflight(base,candidate,self.symbols())['verdict'],'STREAM_PREFLIGHT_PASS')
        self.point(base,0,0x23fc75)
        self.assertEqual(sheets.ownership_preflight(base,candidate,self.symbols())['verdict'],'HOLD')

    def test_current_base_packet(self):
        base=os.environ.get('SHEET_PREFLIGHT_BASE')
        if not base: self.skipTest('real input packet paths not supplied')
        run=subprocess.run([sys.executable,str(Path(sheets.__file__)),base,
            '--ownership-candidate',os.environ['SHEET_PREFLIGHT_CANDIDATE'],
            '--ownership-symbols',os.environ['SHEET_PREFLIGHT_SYMBOLS'],
            '--expected-base-sha256','bcd74deab0db00c3a46f80fe214c0adb5aa30ab8b7c28694753d64c89c0cf0a9',
            '--ownership-json',os.environ['SHEET_PREFLIGHT_OUTPUT']],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)


class CliOutputGuards(unittest.TestCase):
    """New CLI boundary fixtures, intentionally separate from accepted5PASS."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.base=self.root/'base.sfc'; self.base.write_bytes(StreamPreflight().fixture())
        self.candidate=self.root/'candidate.sfc'; self.candidate.write_bytes(StreamPreflight().fixture(True))
        self.symbols=self.root/'candidate.sym'; self.symbols.write_text(StreamPreflight().symbols())
        self.inputs=(self.base,self.candidate,self.symbols)
        self.before={p:p.read_bytes() for p in self.inputs}

    def args(self,output):
        return argparse.Namespace(rom=str(self.base), ownership_candidate=str(self.candidate),
            ownership_symbols=str(self.symbols), ownership_json=str(output),
            expected_base_sha256=hashlib.sha256(self.before[self.base]).hexdigest())

    def invoke(self,output):
        stdout,stderr=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            status=sheets.ownership_cli(self.args(output))
        return status,stdout.getvalue(),stderr.getvalue()

    def test_exact_symlink_hardlink_and_lexical_aliases_refuse_before_reads(self):
        for target in self.inputs:
            with self.subTest(input=target.name):
                symlink=self.root/(target.name+'.symlink'); symlink.symlink_to(target)
                hardlink=self.root/(target.name+'.hardlink'); os.link(target,hardlink)
                lexical=target.parent/'subdir'/'..'/target.name
                (target.parent/'subdir').mkdir(exist_ok=True)
                for output in (target,symlink,hardlink,lexical):
                    with mock.patch.object(Path,'read_bytes',side_effect=AssertionError('input read before output validation')):
                        status,_,err=self.invoke(output)
                    self.assertEqual(status,1)
                    refused=json.loads(err)
                    self.assertEqual(refused['verdict'],'HOLD')
                    self.assertFalse(refused['output_reserved'])
                    self.assertIn('id',refused['attempt'])
                self.assertEqual(target.read_bytes(),self.before[target])

    def test_existing_pass_output_is_preserved(self):
        output=self.root/'accepted.json'
        prior=b'{"verdict":"STREAM_PREFLIGHT_PASS","attempt":{"id":"old"}}\n'
        output.write_bytes(prior)
        with mock.patch.object(Path,'read_bytes',side_effect=AssertionError('input read before output validation')):
            status,_,err=self.invoke(output)
        self.assertEqual(status,1)
        self.assertEqual(output.read_bytes(),prior)
        self.assertNotEqual(json.loads(err)['attempt']['id'],'old')

    def test_missing_inputs_get_fresh_hold_json(self):
        for index,target in enumerate(self.inputs):
            target.unlink()
            output=self.root/f'missing{index}.json'
            status,_,_=self.invoke(output)
            record=json.loads(output.read_text())
            self.assertEqual(status,1)
            self.assertEqual(record['verdict'],'HOLD')
            self.assertTrue(record['output_reserved'])
            self.assertIn('FileNotFoundError',record['issues'][0])
            self.assertIn('finished_utc',record['attempt'])
            target.write_bytes(self.before[target])

    def test_unreadable_inputs_get_bounded_hold_json(self):
        original=Path.read_bytes
        for index,target in enumerate(self.inputs):
            def deny(path, target=target):
                if path==target: raise PermissionError('fixture refusal '+('x'*1000))
                return original(path)
            output=self.root/f'unreadable{index}.json'
            with mock.patch.object(Path,'read_bytes',deny):
                status,_,_=self.invoke(output)
            record=json.loads(output.read_text())
            self.assertEqual(status,1)
            self.assertEqual(record['verdict'],'HOLD')
            self.assertIn('PermissionError',record['issues'][0])
            self.assertLess(len(record['issues'][0]),600)

    def test_malformed_symbol_bytes_and_text_get_hold_json(self):
        for index,content in enumerate((b'\xff\xfe',b'not a symbol file\n')):
            self.symbols.write_bytes(content)
            output=self.root/f'malformed{index}.json'
            status,_,_=self.invoke(output)
            record=json.loads(output.read_text())
            self.assertEqual(status,1)
            self.assertEqual(record['verdict'],'HOLD')
            self.assertTrue(record['issues'])
            self.assertIn('id',record['attempt'])

    def test_exclusive_reservation_race_does_not_replace_winner(self):
        output=self.root/'raced.json'
        original=os.open
        def race(path,flags,mode):
            Path(path).write_bytes(b'FOREIGN_WINNER')
            return original(path,flags,mode)
        with mock.patch('os.open',side_effect=race):
            status,_,err=self.invoke(output)
        self.assertEqual(status,1)
        self.assertFalse(json.loads(err)['output_reserved'])
        self.assertEqual(output.read_bytes(),b'FOREIGN_WINNER')

    def test_entrypoint_writes_new_attempt_without_modifying_inputs(self):
        output=self.root/'fresh.json'
        run=subprocess.run([sys.executable,str(Path(sheets.__file__)),str(self.base),
            '--ownership-candidate',str(self.candidate),'--ownership-symbols',str(self.symbols),
            '--expected-base-sha256',hashlib.sha256(self.before[self.base]).hexdigest(),
            '--ownership-json',str(output)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        record=json.loads(output.read_text())
        self.assertEqual(record['verdict'],'STREAM_PREFLIGHT_PASS')
        self.assertTrue(record['output_reserved'])
        self.assertIn('finished_utc',record['attempt'])
        for p in self.inputs:self.assertEqual(p.read_bytes(),self.before[p])


if __name__=='__main__': unittest.main()
