"""Scoped private publisher controls; diagnostic inputs never grant admission."""
import copy
import json
import tempfile
import os
import shutil
import subprocess
from unittest import mock
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Scripts/Build'))
sys.path.insert(0,str(ROOT/'Scripts/Generate'))
import lyra_current_transfer as X
import lyra_native_loaders as L
from test_lyra_private_pilot_boundary import actual_preview_fixture
from test_lyra_project_admission import document
from lyra_project_terrain import parse_terrain_document


class CheckpointPreviewPublisherTests(unittest.TestCase):
    def test_backdrop_org_has_only_the_audited_bank34_manifest_contract(self):
        import generate_hack_manifest as H
        from generate_hooks_json import OrgDirective
        from dataclasses import replace
        directive=OrgDirective('Oracle_ReadOverworldBackdropColor',None,
            'Overworld/lyra_native_loaders.asm:374',proof_bank=0x34)
        H._validate_unresolved_org_proofs([directive],[])
        for changed in (replace(directive,proof_bank=None),replace(directive,proof_bank=0x35),
                        replace(directive,expression='OtherLabel'),
                        replace(directive,source='Overworld/other.asm:374')):
            with self.subTest(changed=changed),self.assertRaises(H.ManifestGenerationError):
                H._validate_unresolved_org_proofs([changed],[])

    def test_hash_bound_bg_constants_repeat_only_exact_selected_context(self):
        import asm_source as S
        with tempfile.TemporaryDirectory() as name:
            root=Path(name).resolve();folder=root/'Data/Generated/lyra_project';folder.mkdir(parents=True)
            (root/'Oracle_main.asm').write_text('incsrc "Data/Generated/lyra_project/runtime_constants.asm"\n')
            constants=folder/'runtime_constants.asm'
            for enabled in (0,1):
                values=dict(PROJECT_BG128_ENABLED=enabled,PROJECT_BG128_RESTORE_BOUND=enabled,
                            PROJECT_BG128_CODE_BASE=0xE0D000,PROJECT_BG128_CODE_END=0xE0D400)
                defines=dict(values,LYRA_BUILD_CONTEXT=1)
                text=''.join(f'!{key} = {value}\n' for key,value in values.items())
                constants.write_text(text)
                self.assertIn(constants,S.collect_reachable_asm_sources(root,defines=defines))
                for key,value in values.items():
                    line=f'!{key} = {value}'
                    self.assertFalse(S._is_identical_build_context_assignment(S.LYRA_CONSTANTS,line,
                        dict(defines,LYRA_BUILD_CONTEXT=0)))
                    self.assertFalse(S._is_identical_build_context_assignment('Overworld/foreign.asm',line,defines))
                    constants.write_text(text.replace(line,line+' + 1'))
                    with self.assertRaisesRegex(S.SourceGraphError,'reassigns preloaded global define'):
                        S.collect_reachable_asm_sources(root,defines=defines)
                    constants.write_text(text)

    def test_compiled_checkpoint_cli_owns_exact_readonly_scope(self):
        import checkpoint_registry as C
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as name:
            rom=Path(name)/'compiled.sfc';rom.write_bytes(bytes(0x400000))
            args=['--root',name,'--base-rom',str(Path(name)/'base.sfc'),'--rom',str(rom)]
            def checked(_):
                self.assertEqual(X._CANDIDATE_INSPECTION.get(),X.Q.bound(rom))
                self.assertTrue(X._new_or_inspected_target(str(rom)))
                return dict(passed=True)
            self.assertFalse(X._new_or_inspected_target(str(rom)))
            with mock.patch.object(C,'check_invocation',side_effect=checked),contextlib.redirect_stdout(io.StringIO()):
                C.main(args)
            self.assertIsNone(X._CANDIDATE_INSPECTION.get())
            self.assertFalse(X._new_or_inspected_target(str(rom)))
            def mutated(_):
                rom.write_bytes(b'changed')
                return dict(passed=True)
            with mock.patch.object(C,'check_invocation',side_effect=mutated):
                with self.assertRaisesRegex(ValueError,'Current saved input changed'):
                    C.main(args)
            self.assertIsNone(X._CANDIDATE_INSPECTION.get())

    def test_review_binds_consumers_while_final_build_owns_whole_image_hash(self):
        rom,symbols,request=actual_preview_fixture(combined=True)
        standalone=L.inspect_seeded_checkpoint_preview(rom,symbols,**request)
        self.assertEqual(standalone['compiled_rom_sha256'],X.R.sha(rom))
        proof=L.inspect_current_consumers(rom,symbols,checkpoint_preview=request)
        self.assertNotIn('compiled_rom_sha256',proof['preview_guards'])
        metadata=bytearray(rom);metadata[0x3F0010]^=1
        self.assertEqual(L.inspect_current_consumers(bytes(metadata),symbols,checkpoint_preview=request),proof)
        code=bytearray(rom);code[X.A.pc(proof['preview_guards']['code_snes'][0])]^=1
        with self.assertRaises(ValueError):
            L.inspect_current_consumers(bytes(code),symbols,checkpoint_preview=request)

    @unittest.skipUnless(os.environ.get('ASAR_BIN') or shutil.which('asar'),'Asar unavailable')
    def test_actual_global_bridge_resolves_the_namespaced_home_owner(self):
        text=(ROOT/'Overworld/lyra_native_loaders.asm').read_text()
        begin=text.index('if defined("LYRA_PRIVATE_CHECKPOINT_ENABLED")')
        end=text.index('if defined("LYRA_PRIVATE_PILOT_BOUNDARIES_ENABLED")',begin)
        bridge=text[begin:end]
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);main=folder/'main.asm';rom=folder/'synthetic.sfc'
            prefix='lorom\n!LYRA_PRIVATE_CHECKPOINT_ENABLED = 1\nnamespace Oracle\norg $34FC54\nCheckpoint_EnterHome = pc()\nRTL\nnamespace off\n'
            for include in (False,True):
                main.write_text(prefix+(bridge if include else '')+'org $E0C000\nJSL Checkpoint_EnterHome\n')
                rom.write_bytes(bytes(0x400000))
                run=subprocess.run([os.environ.get('ASAR_BIN') or shutil.which('asar'),
                    '--no-title-check','--fix-checksum=off',str(main),str(rom)],capture_output=True,text=True)
                if include:
                    self.assertEqual(run.returncode,0,run.stdout+run.stderr)
                    at=X.A.pc(0xE0C000);self.assertEqual(rom.read_bytes()[at:at+4],bytes.fromhex('2254fc34'))
                else:
                    self.assertNotEqual(run.returncode,0)
                    self.assertIn("Label 'Checkpoint_EnterHome' wasn't found",run.stdout+run.stderr)

    def test_distinct_consumer_snapshot_is_required_and_never_broad_readiness(self):
        rom,symbols,request=actual_preview_fixture(combined=True)
        proof=L.inspect_current_consumers(rom,symbols,checkpoint_preview=request)
        self.assertIs(X.require_preview_consumers(proof,request['reviewed'],request['source']),proof)
        self.assertFalse(proof['ordinary_build_ready']);self.assertFalse(proof['runtime_admission'])
        for key,value in (('kind','lyra.current_compiled_consumers.v1'),('ordinary_build_ready',True),
                          ('production_admission',True),('current_core_inspected',False)):
            changed=copy.deepcopy(proof);changed[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'COMPILED_BINDING_REQUIRED'):
                X.require_preview_consumers(changed,request['reviewed'],request['source'])

    def test_guard_snapshot_cannot_drop_holds_or_add_native_proof(self):
        rom,symbols,request=actual_preview_fixture(combined=True)
        proof=L.inspect_current_consumers(rom,symbols,checkpoint_preview=request)
        for key,value in (('native_gameplay_verified',True),('runtime_admission',True),
                          ('held_routes',[]),('credits_held',[]),('code_snes',[0,1]),
                          ('reviewed_binding_sha256','0'*64)):
            changed=copy.deepcopy(proof);changed['preview_guards'][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'COMPILED_BINDING_REQUIRED'):
                X.require_preview_consumers(changed,request['reviewed'],request['source'])
        for key in ('guard_source_sha256','source_rom_sha256'):
            guard=copy.deepcopy(request['reviewed']);guard[key]='0'*64
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'SOURCE_STALE'):
                X.require_preview_consumers(proof,guard,request['source'])

    def test_preview_derives_only_the_explicit_human_pair_without_project_write(self):
        raw=document();parsed=parse_terrain_document(X.P.encoded(raw),raw['profile'],allow_authoring_drafts=True)
        before=copy.deepcopy(parsed);pilot=X.native_checkpoint_boundaries(parsed)
        self.assertEqual(pilot['selected_areas'],[
            dict(parent_map_id=a,size='small',maps=[a]) for a in (0xA0,0xA1)])
        self.assertEqual(parsed,before);self.assertEqual(len(parsed.maps),32)
        self.assertFalse(parsed.gameplay_areas);self.assertEqual(len(pilot['unselected_tail_maps']),30)

    def test_policy_route_reaches_real_binding_interface_and_propagates_its_refusal(self):
        # Unit dispatch test stops at the binding refusal. It supplies no source
        # authorization, destination, producer grant or successful private plan.
        import checkpoint_registry as C
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);ledger=folder/'ledger.json';review=folder/'review.json'
            review.write_bytes(X.P.encoded(dict(kind=X.REVIEW_KIND)))
            bound=dict(path=str(folder/'not-admitted'),sha256='0'*64)
            runtime=dict(kind=X.PREVIEW_POLICY_KIND,scope=X.PREVIEW_SCOPE,runtime_admission=True,
                review_file=str(review),tail_recipe=bound,graphics_source=bound,graphics_assets=[],
                compiled_consumers=bound,event_state={},origin_preimages=[],guard_binding=bound,
                private_checkpoint=dict(plan=bound,landing=bound))
            request=dict(allocation_policy_id='unit-refusal-only')
            def install(value):
                ledger.write_bytes(X.P.encoded(dict(current_save_transfer_policies=[
                    dict(id=request['allocation_policy_id'],current_runtime=value)])))
            profile=object();source=b'unit refusal, never a qualified source'
            with mock.patch.object(X.R,'LEDGER',ledger), \
                 mock.patch.object(X,'verify_transfer',return_value=(request,source,None)), \
                 mock.patch.object(X,'current_native_source_profile',return_value=profile), \
                 mock.patch.object(C,'bind_private_preview',create=True,
                                   side_effect=ValueError('PRIVATE_LANDING_UNBOUND')) as bind:
                install(runtime)
                with self.assertRaisesRegex(ValueError,'PRIVATE_LANDING_UNBOUND'):
                    X.ordinary_plan('project','base','request')
                bind.assert_called_once_with('project','base','request',profile,bound,bound)
                for change in ({'scope':'disposable_build_only'},{'runtime_admission':False},
                               {'private_checkpoint':{'plan':bound}},
                               {'private_pilot':bound},{'kind':'lyra.current_runtime_policy.v1'}):
                    bind.reset_mock();bad=copy.deepcopy(runtime);bad.update(change);install(bad)
                    with self.subTest(change=change),self.assertRaises(ValueError):
                        X.ordinary_plan('project','base','request')
                    bind.assert_not_called()

    def test_checkpoint_symbol_adapter_uses_existing_strict_parser(self):
        symbols=b'[labels]\n34:F900 Oracle_Checkpoint_StateCodeBegin\n34:FC54 Oracle_Checkpoint_EnterHome\n'
        self.assertEqual(X.checkpoint_symbols(symbols)['Oracle_Checkpoint_EnterHome'],0x34FC54)
        with self.assertRaisesRegex(ValueError,'Conflicting WLA symbol'):
            X.checkpoint_symbols(symbols+b'34:FC55 Oracle_Checkpoint_EnterHome\n')
        with self.assertRaises(ValueError):X.checkpoint_symbols(b'[labels]\nmalformed\n')


if __name__=='__main__':unittest.main()
