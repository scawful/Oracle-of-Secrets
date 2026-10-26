'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const zlib = require('node:zlib');
const { spawnSync } = require('node:child_process');
const { evaluateRecipe, pixelSha256 } = require('../../Scripts/Graphics/sprite_pose');
const { renderArtifacts } = require('../../Scripts/Graphics/sprite_pose_render');
const ROOT = path.resolve(__dirname, '../..');
const CLI = path.join(ROOT, 'Scripts/Graphics/sprite_pose.js');
const fixture = name => JSON.parse(fs.readFileSync(path.join(ROOT, `Scripts/Graphics/examples/${name}.recipe.json`), 'utf8'));
const tiny = () => fixture('tiny');

test('approved three poses replay their reviewed pixel hashes exactly', () => {
  const recipe = fixture('ganondorf-three-pose'), result = evaluateRecipe(recipe);
  assert.deepEqual(Object.fromEntries(Object.entries(result.frames).map(([name, frame]) => [name, frame.pixelSha256])), {
    base: '0dcb4f9ed4260bdafd5419a3c9ae50c2cb36d3cf3b9883e1fdc34945f1bd1b21',
    mid: 'be751bac119f89325c9a7fc58d54cde3aad7ca9781fac503f441266bb7da49c7',
    lifted: '5ac0b37e01278f53e4fb7e08def74bcd791c53826a0f446df893574143acf606'
  });
  assert.equal(Object.keys(result.frames).length, 3);
  assert.deepEqual(result.frames.base.pixels, recipe.pixels);
  assert.equal(result.segments.reduce((sum, segment) => sum + segment.pixels.length, 0), 540);
});

test('different dimensions/palette and nonzero transparency rotate without losing opaque index zero', () => {
  const result = evaluateRecipe(tiny());
  assert.deepEqual(result.frames.turn.pixels, [
    2,2,2,2,2,2,
    2,2,2,1,0,2,
    2,2,2,0,3,2,
    2,2,2,2,2,2,
    0,0,0,0,0,0
  ]);
  assert.deepEqual(result.frames.turn.placements.body.destinationAnchor, [4, 2]);
});

test('source overlap uses priority, then later definition for equal priorities', () => {
  for (const [priority, expected] of [[4, 'body'], [5, 'overlap'], [6, 'overlap']]) {
    const recipe = tiny();
    recipe.segments.push({ id: 'overlap', rect: [1,1,1,1], priority });
    recipe.layerOrder.push('overlap');
    const result = evaluateRecipe(recipe);
    assert.equal(result.ownerByPixel[7], expected);
    assert.equal(result.segments.reduce((sum, segment) => sum + segment.pixels.length, 0), 10);
  }
});

test('destination layer order controls occlusion independently of source ownership', () => {
  const recipe = { schema:1, width:3, height:1, palette:[[0,0,0],[10,20,30],[40,50,60]], transparentIndex:0, pixels:[1,0,2], segments:[{id:'a',rect:[0,0,1,1]},{id:'b',rect:[2,0,1,1]}], layerOrder:['a','b'], poses:{ overlap:{segments:{a:{to:[1,0]},b:{to:[1,0]}}} } };
  assert.deepEqual(evaluateRecipe(recipe).frames.overlap.pixels, [0,2,0]);
  recipe.layerOrder.reverse();
  assert.deepEqual(evaluateRecipe(recipe).frames.overlap.pixels, [0,1,0]);
});

test('extract before painting clears the old shoulder and preserves the real head', () => {
  const recipe = { schema:1,width:5,height:5,palette:[[0,0,0],[100,150,50],[60,40,80]],transparentIndex:0,pixels:[0,0,0,0,0,0,1,0,0,0,0,0,0,2,0,0,0,0,2,0,0,0,0,0,0],segments:[{id:'head',rect:[1,1,1,1]},{id:'arm',rect:[3,2,1,2]}],poses:{base:{},lifted:{segments:{arm:{to:[4,0]}}}},protectedRegions:[{rect:[1,1,1,1]}],baselinePose:'base' };
  const result = evaluateRecipe(recipe);
  assert.equal(result.frames.lifted.pixels[2*5+3], 0);
  assert.equal(result.frames.lifted.pixels[3*5+3], 0);
  assert.equal(result.frames.lifted.pixels[6], 1);
  assert.equal(result.frames.lifted.pixels[4], 2);
  assert.equal(result.frames.lifted.pixels[9], 2);
});

test('explicit destination clips discard only authorized pixels, repairs are checked and reported', () => {
  const recipe = tiny();
  recipe.poses.turn.segments.body = { to:[-1,1], clip:[0,0,6,5] };
  recipe.poses.turn.repairs = [{x:5,y:0,index:1,reason:'one local join'}];
  const result = evaluateRecipe(recipe);
  assert.equal(result.frames.turn.placements.body.clippedPixels, 2);
  assert.equal(result.frames.turn.pixels[5], 1);
  assert.deepEqual(result.frames.turn.repairs[0], {x:5,y:0,index:1,reason:'one local join',before:2});
  assert.deepEqual(result.frames.turn.pixels.slice(24), [0,0,0,0,0,0]);
});

test('invalid coordinates, palettes, references, effects and protections fail before output', async t => {
  const cases = [
    ['missing schema', r => delete r.schema, /schema/],
    ['unsupported schema', r => r.schema = 2, /schema/],
    ['zero size', r => r.width = 0, /width\/height/],
    ['bad RGB', r => r.palette[0][0] = 256, /palette/],
    ['bad pixel', r => r.pixels[0] = 4, /pixels/],
    ['wrong length', r => r.pixels.pop(), /pixels/],
    ['bad transparency', r => r.transparentIndex = -1, /transparentIndex/],
    ['negative rect', r => r.segments[0].rect[0] = -1, /rectangle/],
    ['fractional rect', r => r.segments[0].rect[0] = 0.5, /rectangle/],
    ['outside rect', r => r.segments[0].rect[2] = 7, /rectangle/],
    ['unowned pixel', r => r.segments[0].rect = [0,4,5,1], /no segment owner/],
    ['unknown segment', r => r.poses.turn.segments.typo = {dx:1}, /unknown segment/],
    ['unknown field', r => r.poses.turn.segments.body = {dxx:1}, /unknown transform field/],
    ['duplicate layer', r => r.layerOrder = ['body','body'], /layerOrder/],
    ['ambiguous transform', r => r.poses.turn.segments.body = {to:[3,1],dx:1}, /to or dx\/dy/],
    ['unsupported rotation', r => r.poses.turn.segments.body.rotation = 90, /rotation/],
    ['outside effect', r => r.poses.turn.segments.body.to = [9,9], /outside canvas/],
    ['bad clip', r => r.poses.turn.segments.body.clip = [0,0,7,5], /rectangle/],
    ['outside repair', r => r.poses.turn.repairs = [{x:6,y:1,index:1}], /repair/],
    ['repair color', r => r.poses.turn.repairs = [{x:1,y:1,index:4}], /repair/],
    ['protected region', r => r.poses.turn.repairs = [{x:0,y:4,index:1}], /protected source region/],
    ['unknown sequence', r => r.sequence[0].pose = 'absent', /sequence/],
    ['wrong expected pixels', r => r.expectedPixelSha256 = {turn:'0'.repeat(64)}, /pixel SHA256 mismatch/]
  ];
  for (const [label, change, error] of cases) await t.test(label, () => {
    const recipe = tiny(); change(recipe); assert.throws(() => evaluateRecipe(recipe), error);
  });
});

test('evaluation leaves frozen input intact and returned arrays do not alias it', () => {
  const recipe = tiny(), before = JSON.stringify(recipe);
  const freeze = object => { if (object && typeof object === 'object') { Object.values(object).forEach(freeze); Object.freeze(object); } };
  freeze(recipe);
  const result = evaluateRecipe(recipe);
  result.frames.base.pixels[0] = 1;
  result.palette[0][0] = 99;
  result.segments.find(segment => segment.id === 'body').anchor[0] = 99;
  result.segments[0].pixels[0][2] = 3;
  assert.equal(JSON.stringify(recipe), before);
});

function decodePng(buffer) {
  assert.deepEqual(buffer.subarray(0,8), Buffer.from([137,80,78,71,13,10,26,10]));
  const width = buffer.readUInt32BE(16), height = buffer.readUInt32BE(20), compressed = [];
  for (let offset = 8; offset < buffer.length;) {
    const size = buffer.readUInt32BE(offset), name = buffer.toString('ascii',offset+4,offset+8);
    if (name === 'IDAT') compressed.push(buffer.subarray(offset+8,offset+8+size));
    offset += size + 12;
  }
  return {width,height,rows:zlib.inflateSync(Buffer.concat(compressed))};
}

test('PNG rendering preserves native RGB, transparency and square integer pixels', () => {
  const result = evaluateRecipe(tiny()), files = renderArtifacts(result, 2), image = decodePng(files['pose-base.png']);
  assert.equal(image.width, 12); assert.equal(image.height, 10);
  const pixel = (x,y) => [...image.rows.subarray(y*(image.width*4+1)+1+x*4,y*(image.width*4+1)+1+x*4+4)];
  assert.deepEqual(pixel(0,0), [0,0,0,0]);
  assert.deepEqual(pixel(2,2), [70,180,150,255]);
  assert.deepEqual(pixel(3,3), [70,180,150,255]);
  assert.deepEqual(pixel(4,2), [12,24,36,255]);
  assert.ok(files['atlas.png']); assert.ok(files['contact.png']);
});

test('CLI help/intake work and existing input/output artifacts cannot be overwritten', t => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'sprite-pose-test-'));
  t.after(() => fs.rmSync(temp, {recursive:true,force:true}));
  const input = path.join(temp,'input.json'), out = path.join(temp,'preview');
  fs.writeFileSync(input, JSON.stringify(tiny()));
  const before = fs.readFileSync(input);
  const run = args => spawnSync(process.execPath,[CLI,...args],{encoding:'utf8'});
  assert.equal(run(['--help']).status,0);
  assert.match(run([]).stderr,/--recipe and --out/);
  const completed = run(['--recipe',input,'--out',out,'--scale','2']);
  assert.equal(completed.status,0,completed.stderr);
  assert.deepEqual(fs.readFileSync(input),before);
  assert.equal(run(['--recipe',input,'--out',input]).status,1);
  assert.equal(run(['--recipe',input,'--out',out]).status,1);
  const output = JSON.parse(fs.readFileSync(path.join(out,'poses.json')));
  assert.equal(output.frames.base.pixelSha256,pixelSha256(tiny().pixels));
  assert.ok(fs.existsSync(path.join(out,'atlas.png')));
  const invalid = path.join(temp,'bad.json'), rejected = path.join(temp,'rejected');
  const bad = tiny(); bad.poses.turn.segments.missing = {dx:1}; fs.writeFileSync(invalid,JSON.stringify(bad));
  assert.equal(run(['--recipe',invalid,'--out',rejected]).status,1);
  assert.equal(fs.existsSync(rejected),false);
});
