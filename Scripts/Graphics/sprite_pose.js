#!/usr/bin/env node
'use strict';

// Indexed-pixel pose authoring. Recipes contain all sprite-specific coordinates.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const fail = message => { throw new Error(message); };
const integer = n => Number.isSafeInteger(n);
const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const pixelSha256 = pixels => crypto.createHash('sha256').update(Buffer.from(pixels)).digest('hex');
const inside = ([x, y, width, height], px, py) => px >= x && px < x + width && py >= y && py < y + height;

function validateRect(rect, width, height, label) {
  if (!Array.isArray(rect) || rect.length !== 4 || !rect.every(integer) ||
      rect[0] < 0 || rect[1] < 0 || rect[2] <= 0 || rect[3] <= 0 ||
      rect[0] + rect[2] > width || rect[1] + rect[3] > height) {
    fail(`${label}: expected an in-canvas, half-open [x,y,width,height] rectangle`);
  }
}

function validateTransform(transform, width, height, label) {
  if (!isObject(transform)) fail(`${label}: expected a transform object`);
  if (Object.keys(transform).some(key => !['dx', 'dy', 'to', 'rotation', 'clip'].includes(key))) fail(`${label}: unknown transform field`);
  for (const key of ['dx', 'dy']) {
    if (transform[key] !== undefined && !integer(transform[key])) fail(`${label}.${key}: expected an integer`);
  }
  if (transform.to !== undefined && (!Array.isArray(transform.to) || transform.to.length !== 2 || !transform.to.every(integer))) {
    fail(`${label}.to: expected integer [x,y]`);
  }
  if (transform.to !== undefined && (transform.dx !== undefined || transform.dy !== undefined)) {
    fail(`${label}: use to or dx/dy, not both`);
  }
  if (transform.rotation !== undefined && ![0, 180].includes(transform.rotation)) fail(`${label}.rotation: supported values are 0 and 180`);
  if (transform.clip !== undefined) validateRect(transform.clip, width, height, `${label}.clip`);
}

function evaluateRecipe(recipe) {
  if (!isObject(recipe)) fail('Recipe must be an object');
  if (recipe.schema !== 1) fail('schema: expected supported recipe version 1');
  const { width, height, palette, transparentIndex, pixels, segments, poses } = recipe;
  if (!integer(width) || !integer(height) || width <= 0 || height <= 0 || width * height > 1048576) {
    fail('width/height: expected positive integers totaling at most 1048576 source pixels');
  }
  if (!Array.isArray(palette) || palette.length < 1 || palette.length > 256 ||
      !palette.every(rgb => Array.isArray(rgb) && rgb.length === 3 && rgb.every(c => integer(c) && c >= 0 && c <= 255))) {
    fail('palette: expected 1 to 256 RGB triplets with integer channels 0..255');
  }
  const validIndex = index => integer(index) && index >= 0 && index < palette.length;
  if (!validIndex(transparentIndex)) fail('transparentIndex: outside palette');
  if (!Array.isArray(pixels) || pixels.length !== width * height || !pixels.every(validIndex)) fail('pixels: wrong length or invalid palette index');
  if (!Array.isArray(segments) || segments.length === 0) fail('segments: expected a nonempty array');
  const byId = new Map();
  const validId = id => typeof id === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(id);
  for (const segment of segments) {
    if (!isObject(segment) || !validId(segment.id) || byId.has(segment.id)) fail('segments: invalid or duplicate id');
    validateRect(segment.rect, width, height, `segment ${segment.id}`);
    if (segment.priority !== undefined && !integer(segment.priority)) fail(`segment ${segment.id}.priority: expected an integer`);
    if (segment.anchor !== undefined && (!Array.isArray(segment.anchor) || segment.anchor.length !== 2 || !segment.anchor.every(integer))) {
      fail(`segment ${segment.id}.anchor: expected integer [x,y]`);
    }
    if (segment.clip !== undefined) validateRect(segment.clip, width, height, `segment ${segment.id}.clip`);
    byId.set(segment.id, segment);
  }
  const layerOrder = recipe.layerOrder ?? segments.map(segment => segment.id);
  if (!Array.isArray(layerOrder) || layerOrder.length !== segments.length || new Set(layerOrder).size !== segments.length || layerOrder.some(id => !byId.has(id))) {
    fail('layerOrder: name every segment exactly once');
  }
  if (!isObject(poses) || Object.keys(poses).length === 0) fail('poses: expected named pose objects');
  for (const [name, pose] of Object.entries(poses)) {
    if (!validId(name) || !isObject(pose)) fail(`pose ${name}: invalid name or object`);
    if (pose.default !== undefined) validateTransform(pose.default, width, height, `pose ${name}.default`);
    if (pose.default?.to !== undefined) fail(`pose ${name}.default: to belongs on a named segment`);
    if (pose.segments !== undefined && !isObject(pose.segments)) fail(`pose ${name}.segments: expected an object`);
    for (const [id, transform] of Object.entries(pose.segments ?? {})) {
      if (!byId.has(id)) fail(`pose ${name}: unknown segment ${id}`);
      validateTransform(transform, width, height, `pose ${name}/${id}`);
    }
    if (pose.repairs !== undefined && !Array.isArray(pose.repairs)) fail(`pose ${name}.repairs: expected an array`);
    for (const repair of pose.repairs ?? []) {
      if (!isObject(repair) || !integer(repair.x) || !integer(repair.y) || repair.x < 0 || repair.x >= width || repair.y < 0 || repair.y >= height || !validIndex(repair.index)) {
        fail(`pose ${name}: repair coordinate/index outside canvas or palette`);
      }
    }
  }
  const protectedRegions = recipe.protectedRegions ?? [];
  if (!Array.isArray(protectedRegions)) fail('protectedRegions: expected an array');
  for (const region of protectedRegions) {
    if (!isObject(region)) fail('protectedRegions: expected region objects');
    validateRect(region.rect, width, height, 'protected region');
    if (region.poses !== undefined && (!Array.isArray(region.poses) || region.poses.some(name => !Object.hasOwn(poses, name)))) fail('protected region: unknown pose');
  }
  if (recipe.baselinePose !== undefined && !Object.hasOwn(poses, recipe.baselinePose)) fail('baselinePose: unknown pose');
  if (recipe.expectedPixelSha256 !== undefined && !isObject(recipe.expectedPixelSha256)) fail('expectedPixelSha256: expected pose/hash object');
  for (const [name, hash] of Object.entries(recipe.expectedPixelSha256 ?? {})) {
    if (!Object.hasOwn(poses, name) || typeof hash !== 'string' || !/^[a-f0-9]{64}$/.test(hash)) fail('expectedPixelSha256: invalid pose/hash');
  }
  if (recipe.sequence !== undefined && (!Array.isArray(recipe.sequence) || recipe.sequence.some(step => !isObject(step) || !Object.hasOwn(poses, step.pose) || !integer(step.ticks) || step.ticks <= 0))) {
    fail('sequence: expected known poses and positive integer ticks');
  }
  const tickRate = recipe.tickRate ?? 60;
  if (!integer(tickRate) || tickRate <= 0 || tickRate > 1000) fail('tickRate: expected an integer from 1 to 1000');

  // Later definition wins equal-priority overlaps. Extract all original pixels
  // once, before any destination is cleared or painted.
  const ownerByPixel = Array(pixels.length).fill(null);
  const priority = id => byId.get(id).priority ?? 0;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const index = y * width + x;
    if (pixels[index] === transparentIndex) continue;
    for (const segment of segments) {
      const previous = ownerByPixel[index];
      if (inside(segment.rect, x, y) && (previous === null || (segment.priority ?? 0) >= priority(previous))) ownerByPixel[index] = segment.id;
    }
    if (ownerByPixel[index] === null) fail(`Opaque source pixel (${x},${y}) has no segment owner`);
  }
  const extracted = new Map(segments.map(segment => [segment.id, []]));
  ownerByPixel.forEach((id, index) => {
    if (id !== null) extracted.get(id).push([index % width, Math.floor(index / width), pixels[index]]);
  });

  const frames = {};
  for (const [name, pose] of Object.entries(poses)) {
    const output = Array(pixels.length).fill(transparentIndex);
    const outputOwners = Array(pixels.length).fill(null);
    const placements = {};
    for (const id of layerOrder) {
      const segment = byId.get(id);
      const transform = { dx: 0, dy: 0, rotation: 0, ...pose.default, ...pose.segments?.[id] };
      const [sx, sy, sw, sh] = segment.rect;
      const [tx, ty] = transform.to ?? [sx + transform.dx, sy + transform.dy];
      const clip = transform.clip ?? segment.clip;
      let clippedPixels = 0;
      for (const [x, y, color] of extracted.get(id)) {
        let localX = x - sx, localY = y - sy;
        if (transform.rotation === 180) { localX = sw - 1 - localX; localY = sh - 1 - localY; }
        const xx = tx + localX, yy = ty + localY;
        if (clip !== undefined && !inside(clip, xx, yy)) { clippedPixels++; continue; }
        if (xx < 0 || xx >= width || yy < 0 || yy >= height) fail(`pose ${name}/${id}: destination pixel (${xx},${yy}) outside canvas; use an explicit clip to discard it`);
        const index = yy * width + xx;
        output[index] = color;
        outputOwners[index] = id;
      }
      const anchor = segment.anchor;
      const destinationAnchor = anchor ? [tx + (transform.rotation === 180 ? sw - 1 - (anchor[0] - sx) : anchor[0] - sx), ty + (transform.rotation === 180 ? sh - 1 - (anchor[1] - sy) : anchor[1] - sy)] : undefined;
      placements[id] = { sourceRect: [...segment.rect], destination: [tx, ty], dx: tx - sx, dy: ty - sy, rotation: transform.rotation, ...(anchor ? { sourceAnchor: [...anchor], destinationAnchor } : {}), ...(clip ? { clip: [...clip] } : {}), sourcePixels: extracted.get(id).length, clippedPixels };
    }
    const repairs = [];
    for (const repair of pose.repairs ?? []) {
      const index = repair.y * width + repair.x;
      repairs.push({ ...repair, before: output[index] });
      output[index] = repair.index;
      outputOwners[index] = 'repair';
    }
    for (const region of protectedRegions) {
      if (region.poses && !region.poses.includes(name)) continue;
      const [x, y, rw, rh] = region.rect;
      for (let yy = y; yy < y + rh; yy++) for (let xx = x; xx < x + rw; xx++) {
        const index = yy * width + xx;
        if (output[index] !== pixels[index]) fail(`pose ${name}: protected source region changed at (${xx},${yy})`);
      }
    }
    const hash = pixelSha256(output);
    if (recipe.expectedPixelSha256?.[name] && hash !== recipe.expectedPixelSha256[name]) fail(`pose ${name}: pixel SHA256 mismatch: ${hash}`);
    if (name === recipe.baselinePose && output.some((color, i) => color !== pixels[i])) fail(`baseline pose ${name}: differs from source pixels`);
    frames[name] = { pixels: output, pixelSha256: hash, placements, repairs, ownerByPixel: outputOwners };
  }
  return { schema: 1, name: recipe.name ?? 'Sprite poses', width, height, palette: palette.map(rgb => [...rgb]), transparentIndex, sourcePixels: [...pixels], sourcePixelSha256: pixelSha256(pixels), ownershipRule: 'Higher priority wins; later definition wins equal priority', segments: segments.map(segment => ({ ...structuredClone(segment), pixels: extracted.get(segment.id).map(pixel => [...pixel]) })), ownerByPixel, layerOrder: [...layerOrder], frames, sequence: structuredClone(recipe.sequence ?? []), tickRate };
}

const HELP = `Usage: node Scripts/Graphics/sprite_pose.js --recipe FILE.json --out NEW_DIRECTORY [--scale 8] [--gif]

Evaluate native indexed sprite pixels and render poses, a contact sheet and a
labelled segment atlas. No packages, ROM access or image editor are required.

  --recipe FILE   Self-contained indexed source and rectangle/pose recipe
  --out DIR       Required new directory; existing paths are never overwritten
  --scale N       Integer nearest-neighbor scale, 1..32 (default 8)
  --gif           Also make a sequence GIF using an existing ffmpeg executable
  --help          Show this help

Start with Scripts/Graphics/examples/tiny.recipe.json.
See Scripts/Graphics/README.md for coordinates, ownership and intake steps.
`;

function main(argv) {
  if (argv.includes('--help')) { process.stdout.write(HELP); return; }
  const options = { scale: 8, gif: false };
  for (let i = 0; i < argv.length; i++) {
    const flag = argv[i];
    if (flag === '--gif') options.gif = true;
    else if (['--recipe', '--out', '--scale'].includes(flag)) {
      if (!argv[i + 1] || argv[i + 1].startsWith('--')) fail(`${flag}: missing value`);
      options[flag.slice(2)] = argv[++i];
    } else fail(`Unknown option: ${flag}`);
  }
  if (!options.recipe || !options.out) fail('--recipe and --out are required; use --help');
  options.scale = Number(options.scale);
  if (!integer(options.scale) || options.scale < 1 || options.scale > 32) fail('--scale: expected integer 1..32');
  const inputPath = fs.realpathSync(options.recipe), outputPath = path.resolve(options.out);
  if (fs.existsSync(outputPath)) fail('--out: path already exists; choose a new directory');
  const recipe = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
  const result = evaluateRecipe(recipe);
  if (options.gif && result.sequence.length === 0) fail('--gif: recipe needs a nonempty sequence');
  if (options.gif && spawnSync('ffmpeg', ['-version'], { stdio: 'ignore' }).status !== 0) fail('--gif: ffmpeg is unavailable; install nothing or rerun without --gif');
  const { renderArtifacts } = require('./sprite_pose_render');
  const artifacts = renderArtifacts(result, options.scale);
  fs.mkdirSync(outputPath); // No recursive or replace mode; protects all input artifacts.
  for (const [filename, data] of Object.entries(artifacts)) fs.writeFileSync(path.join(outputPath, filename), data, { flag: 'wx' });
  fs.writeFileSync(path.join(outputPath, 'poses.json'), JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
  if (options.gif) {
    let concat = result.sequence.map(step => `file pose-${step.pose}.png\nduration ${step.ticks / result.tickRate}\n`).join('');
    concat += `file pose-${result.sequence[0].pose}.png\n`;
    fs.writeFileSync(path.join(outputPath, 'sequence.ffconcat'), concat, { flag: 'wx' });
    const duration = result.sequence.reduce((sum, step) => sum + step.ticks, 0) / result.tickRate;
    const encoded = spawnSync('ffmpeg', ['-nostdin', '-n', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', 'sequence.ffconcat', '-filter_complex', `fps=${result.tickRate},split[a][b];[a]palettegen[p];[b][p]paletteuse=dither=none`, '-t', String(duration), '-loop', '0', 'sequence.gif'], { cwd: outputPath, encoding: 'utf8' });
    if (encoded.status !== 0) fail(`ffmpeg failed; PNG/JSON output remains in ${outputPath}: ${encoded.stderr || encoded.error?.message}`);
  }
  process.stdout.write(JSON.stringify({ output: outputPath, poses: Object.fromEntries(Object.entries(result.frames).map(([name, frame]) => [name, frame.pixelSha256])) }, null, 2) + '\n');
}

if (require.main === module) {
  try { main(process.argv.slice(2)); } catch (error) { process.stderr.write(`sprite_pose: ${error.message}\n`); process.exitCode = 1; }
}
module.exports = { evaluateRecipe, pixelSha256, main };
