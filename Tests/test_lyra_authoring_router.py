"""Copied-project router, real current backend/stager and shell output mapping.

The inherited external editor/native verifier and registry are host fixtures.
This does not create a real producer receipt or execute Asar/native gameplay.
"""
import configparser
import copy
import os
from pathlib import Path
import subprocess
import unittest
from unittest import mock

from test_lyra_current_build import CurrentBuildTest
import test_lyra_current_transfer as transfer_fixtures
import lyra_current_transfer as X
import authoring_bundle_build as B

ROOT=Path(__file__).resolve().parents[1]


class CurrentAuthoringRouterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original=transfer_fixtures.CurrentSaveTransferTest.prepare
        def copied_route(case,**kwargs):
            case.output=case.root/'router-transfer1'
            case.candidate=case.root/'engine/Roms/generation1/oos168x.sfc'
            configure_saved_target(case)
            return original(case,**kwargs)
        with mock.patch.object(transfer_fixtures.CurrentSaveTransferTest,'prepare',copied_route):
            CurrentBuildTest.setUpClass.__func__(cls)
        # The owned fixture engine is separately reviewed. This link only puts
        # its existing build entry at the bundle's conventional project path.
        (cls.case.project.parent/'project').symlink_to(cls.f.root,target_is_directory=True)

    def shell_paths(self,target):
        # The Python resolver above is real. Only its child-process transport is
        # replaced here; the production Bash output mapping runs unmodified.
        source=ROOT/'Scripts/Build/build_checks.sh'
        command='''set -eu
repo_root="$1";rom_dir="$repo_root/Roms";version=168;base_rom="$2"
patched_rom="$rom_dir/oos168x.sfc";symbols_path=old;mlb_path=old
python3() { [[ "$1" == "$repo_root/Scripts/Build/lyra_project_publisher.py" && "$2" == resolve-target ]] || return 91; printf '%s\\n' "$VERIFIED_TARGET"; }
source "$3"
configure_current_output
printf '%s\\n' "$patched_rom" "$rom_dir" "$receipt_path" "$symbols_path" "$mlb_path" "$annotations_out"
'''
        environment=dict(os.environ,OOS_LYRA_PROJECT=str(self.case.project),OOS_LYRA_REQUEST=str(self.request),
                         OOS_LYRA_CANDIDATE=str(target),VERIFIED_TARGET=str(target))
        environment.pop('OOS_BUILD_RECEIPT',None)
        result=subprocess.run(['bash','-c',command,'router-fixture',str(self.f.root),str(self.case.rom),str(source)],
            env=environment,check=True,text=True,capture_output=True)
        self.assertEqual(result.stdout.splitlines(),[str(target),str(target.parent),
            str(target.parent/'oos168x.build.json'),str(target.with_suffix('.sym')),
            str(target.with_suffix('.mlb')),str(target.parent/'annotations.json')])

    def test_two_native_save_generations_resolve_stage_and_retain_prior_candidate(self):
        case=self.case;engine=self.f.contract_fixture.fixture
        source_before=case.rom.read_bytes();project_before=case.project.read_bytes()
        first=case.candidate;first_request=self.request
        target=X.P.resolve_current_target(case.project)
        self.assertEqual(target['candidate'],str(first))
        original_run=subprocess.run
        def build_only(command,*args,**kwargs):
            if command[0]=='bash':return mock.Mock(returncode=7)
            return original_run(command,*args,**kwargs)
        with mock.patch.object(B.subprocess,'run',side_effect=build_only) as delegate:
            self.assertEqual(B.build_project(case.project),7)
        environment=delegate.call_args.kwargs['env']
        self.assertEqual(environment['OOS_LYRA_CANDIDATE'],str(first))
        self.assertEqual(environment['OOS_BASE_ROM'],str(case.rom))
        self.shell_paths(first)
        folder=self.f.root/X.P.OUTPUT;X.P.write_outputs(folder,self.files)
        self.assertTrue(X.P.stage_current_candidate(folder,first)['rom_written'])
        self.assertEqual(first.read_bytes(),X.A.expanded_rom(source_before))
        metadata=first.parent/'hooks.json';metadata.write_bytes(b'prior generation hooks')
        first_bytes=first.read_bytes()
        with self.assertRaises(ValueError):X.P.resolve_current_target(case.project)
        # Edit supported target/request fields before the next native Save.
        case.output=case.root/'router-transfer2';case.candidate=self.f.root/'Roms/generation2/oos168x.sfc'
        configure_saved_target(case)
        _,self.request=case.prepare();engine.request=self.request
        review=engine.review();self.review_file.write_bytes(X.P.encoded(review))
        proof=X._json(case.enforcement.read_bytes());request=X._json(self.request.read_bytes())
        proof.update(transfer_id=request['transfer_id'],generation=case.save['generation'],
                     operation_id=case.save['operation_id'],save_context=X.Q.bound(case.context_path))
        case.enforcement.write_bytes(X.P.encoded(proof))
        second=X.P.resolve_current_target(case.project)
        self.assertEqual(second['candidate'],str(case.candidate))
        self.shell_paths(case.candidate)
        files=X.P.render_outputs(X.P.make_plan(case.project,case.rom,self.request))
        X.P.write_outputs(folder,files);X.P.stage_current_candidate(folder,case.candidate)
        self.assertEqual(case.candidate.read_bytes(),X.A.expanded_rom(source_before))
        self.assertEqual(first.read_bytes(),first_bytes);self.assertEqual(metadata.read_bytes(),b'prior generation hooks')
        self.assertEqual(case.rom.read_bytes(),source_before)
        self.assertNotEqual(case.project.read_bytes(),project_before) # deliberate fixture Save target update only
        with self.assertRaises(ValueError):X.P.resolve_current_target(case.project,request=first_request)
        # A copied descriptor or changed producer cannot reuse the completed Save.
        copied=case.project.parent/'copied.yaze';copied.write_bytes(case.project.read_bytes())
        with self.assertRaises(ValueError):X.P.resolve_current_target(copied)
        prior=case.producer_path.read_bytes();case.producer_path.write_bytes(b'{}')
        try:
            with self.assertRaises(ValueError):X.P.resolve_current_target(case.project)
        finally:case.producer_path.write_bytes(prior)


def configure_saved_target(case):
    config=configparser.ConfigParser(interpolation=None);config.read(case.project)
    config['files']['lyra_build_request_file']=str(case.output/'request.json')
    config['build']={'build_target':str(case.candidate)}
    with case.project.open('w') as handle:config.write(handle)
    case.inputs['project']=X.Q.bound(case.project)
    case.save['artifacts']=case.artifacts(case.inputs);case.next_save()


if __name__=='__main__':unittest.main()
