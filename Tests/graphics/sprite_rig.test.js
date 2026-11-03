'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { evaluateRecipe } = require('../../Scripts/Graphics/sprite_pose');
const { renderRigArtifacts } = require('../../Scripts/Graphics/sprite_rig');
function fixture() {
  const metadata = { anchor: [1,1], feet: [1,1], hand: null, projectile_origin: null, hurtbox: null, parts: [{id:'wing',kind:'unknown',rect:[0,0,3,2]}] };
  return {schema:1,name:'Moth',width:3,height:2,palette:[[0,0,0],[230,160,30],[30,40,50]],transparentIndex:2,pixels:[2,1,2,1,0,1],segments:[{id:'body',rect:[0,0,3,2]}],poses:{rest:{}},rig:{schema:1,frames:{rest:{pose:'rest',...metadata},flutter:{alias_of:'rest'},other:{pixels:[2,1,2,2,0,2],...metadata}},states:{flight:{source:'fixture timer [3,2,4] at 60Hz',sequence:[{frame:'rest',ticks:3},{frame:'flutter',ticks:2},{frame:'other',ticks:4}]}},reference:{name:'Native reference',source:'portable fixture',width:1,height:2,palette:[[0,0,0],[255,255,255]],transparentIndex:0,pixels:[1,1]}}};
}
test('non-Ganondorf rig preserves nonzero transparency, aliases and source pixels',()=>{
 const r=evaluateRecipe(fixture());assert.deepEqual(r.frames.rest.pixels,r.rig.frames.flutter.pixels);assert.equal(r.rig.frames.flutter.alias_of,'rest');assert.equal(r.rig.frames.other.pixels[3],2);assert.equal(r.rig.states.flight.sequence[0].ticks,3);
});
test('renders native and 4x state sheets and labelled GIF cells',()=>{const a=renderRigArtifacts(evaluateRecipe(fixture()));assert.equal(Object.keys(a).length,5);assert.ok(a['state-flight-1x.png'].subarray(1,4).equals(Buffer.from('PNG')));});
test('rejects alias cycles and missing targets',()=>{for(const target of ['flutter','missing']){const f=fixture();f.rig.frames.flutter.alias_of=target;assert.throws(()=>evaluateRecipe(f),/alias/);}});
test('rejects ambiguous frame sources',()=>{const f=fixture();f.rig.frames.flutter.pose='rest';assert.throws(()=>evaluateRecipe(f),/exactly one/);});
test('requires explicit unknown landmarks and anatomy',()=>{const f=fixture();delete f.rig.frames.rest.hand;assert.throws(()=>evaluateRecipe(f),/hand required/);});
test('rejects unclassified opaque pixels, invalid kind and mask',()=>{
 for(const edit of [p=>p.rect=[0,0,1,1],p=>p.kind='torso',p=>p.mask=[1]]){const f=fixture();edit(f.rig.frames.rest.parts[0]);assert.throws(()=>evaluateRecipe(f),/part|pixel|mask/);}
});
test('validates timing, provenance and duration budgets',()=>{for(const edit of [s=>s.sequence[0].ticks=0,s=>s.source='',s=>s.sequence[0].ticks=36001,s=>s.sequence[0].frame='missing']){const f=fixture();edit(f.rig.states.flight);assert.throws(()=>evaluateRecipe(f),/state|frame|ticks|source|sequence/);}});
test('rejects invalid external pixels, landmarks and reference',()=>{for(const edit of [f=>f.rig.frames.other.pixels[0]=256,f=>f.rig.frames.rest.anchor=[3,0],f=>f.rig.frames.rest.hurtbox=[0,0,-4,1],f=>f.rig.reference.pixels=[]]){const f=fixture();edit(f);assert.throws(()=>evaluateRecipe(f),/pixels|canvas/);}});

test('source geometry may extend beyond visible art without clipping',()=>{const f=fixture();f.rig.frames.rest.projectile_origin=[1,-32];f.rig.frames.rest.hurtbox=[-2,-4,8,9];const r=evaluateRecipe(f);assert.deepEqual(r.rig.frames.rest.hurtbox,[-2,-4,8,9]);});

test('portable recipe runs through CLI and protects existing output',()=>{
 const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'sprite-rig-test-'));
 try {
  const cli=path.resolve(__dirname,'../../Scripts/Graphics/sprite_pose.js'),recipe=path.resolve(__dirname,'../../Scripts/Graphics/examples/non-boss.rig.recipe.json'),out=path.join(temp,'result');
  const run=()=>spawnSync(process.execPath,[cli,'--recipe',recipe,'--out',out,'--scale','1'],{encoding:'utf8'});
  assert.equal(run().status,0);assert.ok(fs.existsSync(path.join(out,'state-test-1x.png')));
  assert.equal(JSON.parse(fs.readFileSync(path.join(out,'poses.json'))).rig.frames.same.alias_of,'rest');
  assert.equal(run().status,1);
 } finally {fs.rmSync(temp,{recursive:true,force:true});}
});
