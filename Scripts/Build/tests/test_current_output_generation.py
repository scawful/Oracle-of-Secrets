"""Real shell builds retain two output generations; backend proof is separate.

The publisher transport and assembler are explicit subprocess fixtures. The
maintained current resolver/stager are exercised in test_lyra_authoring_router.
This suite proves the shell actually creates and records the resolved paths.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
import test_build_pipeline_receipt as fixtures


class CurrentOutputGenerationTest(unittest.TestCase):
    write=fixtures.BuildPipelineReceiptTest.write
    copy=fixtures.BuildPipelineReceiptTest.copy

    def setUp(self):
        fixtures.BuildPipelineReceiptTest.setUp(self)
        self.write('Roms/oos168.sfc','x'*(2*1024*1024))
        self.write('Scripts/Build/lyra_current_transfer.py','def verify_current_context(root,prepared): return {}\n')
        self.write('Scripts/Build/lyra_project_publisher.py','''import hashlib,json,os,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[2];args=sys.argv[1:];command=args[0]
def arg(key):return args[args.index(key)+1]
target=pathlib.Path(os.environ['OOS_LYRA_CANDIDATE'])
if command=='resolve-target':
 assert pathlib.Path(arg('--candidate'))==target and not target.exists()
 print(target);sys.exit(0)
folder=root/'Data/Generated/lyra_project';folder.mkdir(parents=True,exist_ok=True)
if command=='prepare':
 assert pathlib.Path(arg('--candidate'))==target
 constants=b'!LYRA_PROJECT_DATA_PRESENT = 1\\n!LYRA_NATIVE_A1_ENABLED = 0\\n!LYRA_CURRENT_MODE = 1\\n'
 (folder/'runtime_constants.asm').write_bytes(constants)
 (folder/'prepare.json').write_text(json.dumps(dict(kind='lyra.current_build_prepare.v1',selected=True,
  allocation_granted=True,producer_enforcement_verified=True,runtime_admission=True,
  generated_files={'runtime_constants.asm':hashlib.sha256(constants).hexdigest()})))
elif command=='stage':
 assert pathlib.Path(arg('--rom'))==target
 with target.open('xb') as stream:stream.write(pathlib.Path(os.environ['OOS_BASE_ROM']).read_bytes()+bytes(2*1024*1024))
elif command=='verify':
 assert pathlib.Path(arg('--rom'))==target and pathlib.Path(arg('--symbols'))==target.with_suffix('.sym')
 pathlib.Path(arg('--receipt')).write_text('{}')
print('{}')
''')

    def test_two_generation_shell_outputs_and_receipts_are_distinct(self):
        before=(self.root/'Roms/oos168.sfc').read_bytes();first={}
        for generation in (1,2):
            directory=(self.root/f'Roms/current-save-{generation}').resolve();target=directory/'oos168x.sfc'
            self.env.update(OOS_LYRA_PROJECT=str(self.root/'opened.yaze'),OOS_LYRA_REQUEST=str(self.root/'request.json'),
                            OOS_LYRA_CANDIDATE=str(target),OOS_BASE_ROM=str(self.root/'Roms/oos168.sfc'))
            result=subprocess.run(['bash',str(self.root/'Scripts/Build/build_rom.sh'),'168',str(self.assembler)],
                cwd=self.temp.name,env=self.env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            expected=('oos168x.sfc','oos168x.sym','oos168x.mlb','oos168x.build.json',
                      'hooks.json','hack_manifest.json','oos168x.lyra-verification.json')
            self.assertTrue(all((directory/name).is_file() for name in expected))
            receipt=json.loads((directory/'oos168x.build.json').read_bytes())
            self.assertEqual(receipt['artifacts']['output_rom']['path'],str(target))
            self.assertEqual(receipt['artifacts']['hooks']['path'],str(directory/'hooks.json'))
            self.assertEqual(receipt['artifacts']['manifest']['path'],str(directory/'hack_manifest.json'))
            if generation==1:first={p:p.read_bytes() for p in directory.iterdir() if p.is_file()}
            else:self.assertTrue(all(p.read_bytes()==raw for p,raw in first.items()))
        self.assertEqual((self.root/'Roms/oos168.sfc').read_bytes(),before)
        # Real shell stops before opening the prior receipt/output again.
        prior={p:p.read_bytes() for p in directory.iterdir() if p.is_file()}
        retry=subprocess.run(['bash',str(self.root/'Scripts/Build/build_rom.sh'),'168',str(self.assembler)],
            cwd=self.temp.name,env=self.env,text=True,capture_output=True)
        self.assertNotEqual(retry.returncode,0)
        self.assertTrue(all(p.read_bytes()==raw for p,raw in prior.items()))

    def test_unselected_or_foreign_receipt_override_refuses_before_outputs(self):
        target=(self.root/'Roms/current-save-1/oos168x.sfc').resolve()
        for selected in (False,True):
            self.env.update(OOS_LYRA_CANDIDATE=str(target),OOS_BASE_ROM=str(self.root/'Roms/oos168.sfc'))
            if selected:self.env.update(OOS_LYRA_PROJECT=str(self.root/'opened.yaze'),OOS_BUILD_RECEIPT=str(self.root/'foreign.json'))
            result=subprocess.run(['bash',str(self.root/'Scripts/Build/build_rom.sh'),'168',str(self.assembler)],
                cwd=self.temp.name,env=self.env,text=True,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(target.parent.exists());self.assertFalse((self.root/'foreign.json').exists())


if __name__=='__main__':unittest.main()
