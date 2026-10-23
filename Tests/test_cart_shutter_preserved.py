"""Actual-source controls for preserved97 tag17/P ownership; no CPU/native claim."""
import importlib.util
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cart_local_model", ROOT / "Tests/test_cart_shutter_local.py")
local = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(local)
SOURCE = ROOT / "Sprites/Objects/cart_shutter97_preserved.asm"
JOB, SEAL = 0x7E1E88, 0x7E1E89


def linked(name, *dependencies):
    routines = [name, *dependencies]
    entries = {item: ".entry_" + str(i) for i, item in enumerate(routines)}
    lines = []
    for i, item in enumerate(routines):
        lines.append(entries[item])
        code = local.body(SOURCE if item != "CartShutter97_Hold" else local.SOURCE, item)
        labels = {m for line in code for m in re.findall(r"(?<!\w)\.\w+", line)
                  if line.startswith(".")}
        for line in code:
            for label in sorted(labels, key=len, reverse=True):
                line = re.sub(re.escape(label) + r"(?!\w)", ".r" + str(i) + "_" + label[1:], line)
            for target, entry in entries.items():
                line = line.replace("JSR.w " + target, "JSR.w " + entry)
            lines.append(line)
    return local.program(lines)


class Machine(local.Machine):
    def effective(self, operand):
        if operand.endswith(", Y"):
            return int(operand[:-3][1:], 16) + self.y
        return super().effective(operand)


def state(*, preserved=True, original_closed=1, p_open=False, job=0, seal=0xA5):
    m = local.room(closed=bool(original_closed))
    m.update({0xAE: 0x17 if preserved else 0x37, 0xAF: 0x37 if preserved else 0,
              JOB: job, SEAL: seal})
    local.word(m, 0x068C, 0x2020 if p_open else 0)
    for offset, kind in ((0,0), (2,0x18), (4,0x18), (6,0), (18,0), (20,0x18)):
        local.word(m, 0x1980 + offset, kind)
    return m


class PreservedCartShutter(unittest.TestCase):
    def test_room_load_resets_garbage_and_only_clears_p_flags(self):
        code, labels = linked("CartShutter97_InitDoors", "CartShutter97_PreservedProfile")
        for preserved in (False, True):
            for garbage in (0,0x80,0x81,0xFF):
                with self.subTest(preserved=preserved, garbage=garbage):
                    m=state(preserved=preserved,job=garbage,seal=garbage)
                    cpu=Machine(m,p=0,a=0xF000,x=0xCAFE,y=0xBEEF)
                    self.assertEqual(cpu.run(code,labels),"RTL")
                    self.assertEqual(cpu.read(0x068C,True),0xDF00 if preserved else 0xFF00)
                    self.assertEqual((cpu.memory[JOB],cpu.memory[SEAL]),(0,0xA5 if preserved else 0))
                    self.assertEqual((cpu.x,cpu.y,cpu.sp,cpu.p&0x30),(0xCAFE,0xBEEF,0x1FB,0))
                    self.assertNotIn(0x0468,cpu.writes)
                    self.assertNotIn(0x0400,cpu.writes)

    def test_face_filter_is_per_owner_and_fallback_keeps_every_original_type(self):
        code, labels=linked("CartShutter97_FilterDoor","CartShutter97_PreservedProfile","CartShutter97_PJob")
        for preserved in (False,True):
            for job,seal in ((0,0xA5),(0x80,0xA5),(0x81,0xA5),(0xFF,0xA5),(0x80,0)):
                for slot in range(12):
                    with self.subTest(preserved=preserved,job=job,seal=seal,slot=slot):
                        m=state(preserved=preserved,job=job,seal=seal)
                        local.word(m,0x1980+slot*2,0xAB18)
                        cpu=Machine(m,p=0,x=0xCAFE,y=slot*2);cpu.c=True;cpu.v=True
                        self.assertEqual(cpu.run(code,labels),"RTL")
                        owned=job in (0x80,0x81) and seal==0xA5
                        admitted=not preserved or ((slot in (2,10))==owned)
                        self.assertEqual(cpu.a,0x18 if admitted else 0)
                        self.assertEqual((cpu.x,cpu.y,cpu.sp,cpu.p&0x30),(0xCAFE,slot*2,0x1FB,0))
                        self.assertTrue(cpu.c);self.assertTrue(cpu.v)
                        self.assertFalse(cpu.writes)

    def test_animation_restores_original0468_each_call_and_clears_only_finished_job(self):
        code, labels=linked("CartShutter97_Animate","CartShutter97_PreservedProfile","CartShutter97_PJob")
        for original in (0,1):
            for desired in (0,1):
                for finished in (False,True):
                    with self.subTest(original=original,desired=desired,finished=finished):
                        m=state(original_closed=original,job=0x80|desired);m[0x11]=5
                        cpu=Machine(m,p=0x30,x=3,y=5)
                        calls=[]
                        def vanilla(c):
                            calls.append(c.read(0x0468,True))
                            c.write(0x0690,16 if finished else 4,True)
                            c.write(0x11,0 if finished else 5,False)
                            c.p|=0x30
                        cpu.long_stubs={"CartShutter97_AnimateBody":vanilla}
                        self.assertEqual(cpu.run(code,labels),"RTL")
                        self.assertEqual(calls,[desired])
                        self.assertEqual(cpu.read(0x0468,True),original)
                        self.assertEqual(cpu.memory[JOB],0 if finished else 0x80|desired)
                        self.assertEqual((cpu.memory[SEAL],cpu.sp,cpu.p&0x30),(0xA5,0x1FB,0x30))

    def test_no_private_transaction_for_other_header_invalid_job_or_seal(self):
        code,labels=linked("CartShutter97_Animate","CartShutter97_PreservedProfile","CartShutter97_PJob")
        for preserved,job,seal in ((False,0x80,0xA5),(True,0,0xA5),(True,0xFF,0xA5),(True,0x80,0)):
            cpu=Machine(state(preserved=preserved,job=job,seal=seal),p=0)
            self.assertEqual(cpu.run(code,labels),"$01D393")
            self.assertNotIn(0x0468,cpu.writes)
            self.assertNotIn(JOB,cpu.writes)

    def test_open_p_graphic_uses_own_flags_and_original_face_uses0468(self):
        code,labels=linked("CartShutter97_DrawState","CartShutter97_PreservedProfile")
        for original in (0,1):
            for p_open in (False,True):
                for slot in (0,1,2,3,9,10):
                    with self.subTest(original=original,p_open=p_open,slot=slot):
                        cpu=Machine(state(original_closed=original,p_open=p_open),p=0,x=slot*2,y=7)
                        target=cpu.run(code,labels)
                        open_graphic=p_open if slot in (2,10) else not original
                        self.assertEqual(target,"$01B110" if open_graphic else "$01B141")
                        self.assertFalse(cpu.writes)
                        self.assertEqual((cpu.x,cpu.y,cpu.sp),(slot*2,7,0x1FB))

    def test_p_tag_defers_tag17_job_and_never_reads_key_or_selector(self):
        deps=("CartShutter97_PLayout","CartShutter97_Approach","CartShutter97_Hold")
        code,labels=linked("RoomTag_CartShutter97_Preserved",*deps)
        for sub in (5,0x17):
            m=state();m[0x11]=sub
            cpu=Machine(m)
            self.assertEqual(cpu.run(code,labels),"$01CC5A")
            self.assertFalse(cpu.writes)
        for invalid in (0,0xFF):
            cpu=Machine(state(seal=invalid,job=0x80))
            self.assertEqual(cpu.run(code,labels),"$01CC5A")
            self.assertEqual(cpu.writes,{JOB:0})
        m=local.cart(state(),xy=(0x0F80,0x1348),action=2)
        m[0x35]=1;local.word(m,0x22,0x0F7E);local.word(m,0x20,0x1340)
        cpu=Machine(m)
        self.assertEqual(cpu.run(code,labels),"$01CC5A")
        self.assertEqual(cpu.memory[JOB],0x80)
        self.assertEqual(cpu.memory[0x11],5)
        self.assertNotIn(0x0468,cpu.writes)
        self.assertTrue(set(cpu.reads).isdisjoint({0x0400,0x0401,0x0230,0x0231}))
        self.assertTrue(set(cpu.writes).isdisjoint({0x0400,0x0401,0x0230,0x0231}))

    def test_default_off_hooks_and_reserved_wram(self):
        source=SOURCE.read_text();main=local.SOURCE.read_text()
        self.assertIn('incsrc "Sprites/Objects/cart_shutter97_preserved.asm"\nendif',main)
        sys.path.insert(0,str(ROOT/'Scripts/Generate'))
        from asm_source import _iter_active_lines, _load_global_defines
        defines=_load_global_defines(ROOT)
        self.assertEqual(defines['ENABLE_MINECART_CART_SHUTTERS'],0)
        active=list(_iter_active_lines(source.splitlines(),defines))
        self.assertFalse(any(line.lstrip().startswith('org ') for _,line,_ in active))
        defines['ENABLE_MINECART_CART_SHUTTERS']=1
        active=list(_iter_active_lines(source.splitlines(),defines))
        self.assertEqual(sum(line.lstrip().startswith('org ') for _,line,_ in active),5)
        self.assertIn('assert pc() <= $2CF800',source)
        for address in ("01B6DF","01D38F","01D3C7","01B10B"):
            self.assertIn('org $'+address,source)
        symbols=(ROOT/'Core/symbols.asm').read_text()
        self.assertIn('CartShutter97Job  = $7E1E88',symbols)
        self.assertIn('CartShutter97Seal = $7E1E89',symbols)

    def test_source_branch_spans_and_reserved_code_extent(self):
        total=0
        routines=re.findall(r'^(\w+):\n\{',SOURCE.read_text(),re.M)
        for name in routines:
            code,labels=local.program(local.body(SOURCE,name))
            offsets=[];offset=0
            for op,suffix,arg in code:
                offsets.append(offset)
                if op in ('XBA','DEX','INX','CLC','SEC','RTS','RTL','PHP','PLP','PHA','PLA'):
                    size=1
                elif op in ('JML','JSL'):size=4
                elif op in ('JMP','JSR'):size=3
                elif op in ('REP','SEP','BEQ','BNE','BCC','BCS','BPL','BRA'):size=2
                else:size=1+{'b':1,'w':2,'l':3}[suffix]
                offset+=size
            for i,(op,_,arg) in enumerate(code):
                if op in ('BEQ','BNE','BCC','BCS','BPL','BRA'):
                    displacement=offsets[labels[arg]]-offsets[i]-2
                    self.assertTrue(-128<=displacement<=127,(name,op,arg,displacement))
            total+=offset
        self.assertLessEqual(total,0x800)


if __name__ == "__main__":
    unittest.main()
