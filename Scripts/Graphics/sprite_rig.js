'use strict';

// Optional recipe metadata. All anatomy, geometry and timing belong to data.
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { canvas, rect, text, sprite, png } = require('./sprite_pose_render');
const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const validName = v => typeof v === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(v);
const fail = message => { throw new Error(`rig: ${message}`); };
const kinds = new Set(['head', 'hair', 'face', 'arms', 'cape', 'armor', 'weapon', 'projectile', 'shadow', 'unknown']);
function point(value, label, width, height, outside = false) {
  if (!Array.isArray(value) || value.length !== 2 || !value.every(Number.isSafeInteger) || (!outside && (value[0] < 0 || value[0] >= width || value[1] < 0 || value[1] >= height))) fail(`${label}: expected in-canvas [x,y]`);
}
function rectangle(value, label, width, height, outside = false) {
  if (!Array.isArray(value) || value.length !== 4 || !value.every(Number.isSafeInteger) || value[2] <= 0 || value[3] <= 0 || (!outside && (value[0] < 0 || value[1] < 0 || value[0] + value[2] > width || value[1] + value[3] > height))) fail(`${label}: expected in-canvas [x,y,width,height]`);
}
function indexed(image, label) {
  if (!object(image) || !Number.isSafeInteger(image.width) || !Number.isSafeInteger(image.height) || image.width <= 0 || image.height <= 0 || image.width * image.height > 1048576) fail(`${label}: invalid dimensions`);
  if (!Array.isArray(image.palette) || !image.palette.length || image.palette.length > 256 || image.palette.some(rgb => !Array.isArray(rgb) || rgb.length !== 3 || rgb.some(c => !Number.isInteger(c) || c < 0 || c > 255))) fail(`${label}: invalid palette`);
  const valid = n => Number.isInteger(n) && n >= 0 && n < image.palette.length;
  if (!valid(image.transparentIndex) || !Array.isArray(image.pixels) || image.pixels.length !== image.width * image.height || !image.pixels.every(valid)) fail(`${label}: invalid indexed pixels`);
}
function evaluateRig(rig, result) {
  if (!object(rig) || rig.schema !== 1 || !object(rig.frames) || !Object.keys(rig.frames).length || Object.keys(rig.frames).length > 256) fail('schema 1 and 1..256 named frames required');
  const frames = {}, visiting = new Set();
  function resolve(name) {
    if (Object.hasOwn(frames, name)) return frames[name];
    const frame = rig.frames[name];
    if (!validName(name) || !object(frame)) fail(`invalid frame ${name}`);
    if (visiting.has(name)) fail(`alias cycle at ${name}`);
    visiting.add(name);
    const sources = ['pose', 'pixels', 'alias_of'].filter(key => Object.hasOwn(frame, key));
    if (sources.length !== 1) fail(`${name}: choose exactly one pose, pixels or alias_of`);
    let pixels, inherited = {};
    if (frame.alias_of !== undefined) {
      if (!validName(frame.alias_of) || !Object.hasOwn(rig.frames, frame.alias_of)) fail(`${name}: unknown alias target`);
      inherited = resolve(frame.alias_of);
      pixels = inherited.pixels;
    } else if (frame.pose !== undefined) {
      if (!Object.hasOwn(result.frames, frame.pose)) fail(`${name}: unknown pose`);
      pixels = result.frames[frame.pose].pixels;
    } else {
      indexed({ ...result, pixels: frame.pixels }, name);
      pixels = frame.pixels;
    }
    const metadata = { ...inherited, ...structuredClone(frame) };
    for (const key of ['anchor', 'feet', 'hand', 'projectile_origin']) {
      if (!Object.hasOwn(metadata, key)) fail(`${name}: ${key} required; use null when unknown`);
      if (metadata[key] !== null) point(metadata[key], `${name}.${key}`, result.width, result.height, key === 'projectile_origin');
    }
    if (!Object.hasOwn(metadata, 'hurtbox')) fail(`${name}: hurtbox required; use null when unknown`);
    if (metadata.hurtbox !== null) rectangle(metadata.hurtbox, `${name}.hurtbox`, result.width, result.height, true);
    if (!Array.isArray(metadata.parts) || !metadata.parts.length) fail(`${name}: parts required; use kind unknown for unclassified pixels`);
    const partIds = new Set();
    for (const part of metadata.parts) {
      if (!object(part) || !validName(part.id) || partIds.has(part.id) || !kinds.has(part.kind)) fail(`${name}: invalid part id/kind`);
      partIds.add(part.id);
      rectangle(part.rect, `${name}/${part.id}`, result.width, result.height);
      if (part.mask !== undefined && (!Array.isArray(part.mask) || part.mask.length !== part.rect[2] * part.rect[3] || part.mask.some(n => n !== 0 && n !== 1))) fail(`${name}/${part.id}: mask must contain rect-sized 0/1 values`);
    }
    // Require explicit classification, but permit intentional overlapping labels
    // such as face within head. An unknown part may cover unresolved anatomy.
    for (let y = 0; y < result.height; y++) for (let x = 0; x < result.width; x++) {
      if (pixels[y * result.width + x] === result.transparentIndex) continue;
      if (!metadata.parts.some(p => x >= p.rect[0] && y >= p.rect[1] && x < p.rect[0] + p.rect[2] && y < p.rect[1] + p.rect[3] && (!p.mask || p.mask[(y - p.rect[1]) * p.rect[2] + x - p.rect[0]]))) fail(`${name}: unclassified opaque pixel ${x},${y}`);
    }
    frames[name] = { ...metadata, pixels: [...pixels], pixelSha256: crypto.createHash('sha256').update(Buffer.from(pixels)).digest('hex') };
    visiting.delete(name);
    return frames[name];
  }
  Object.keys(rig.frames).forEach(resolve);
  if (!object(rig.states) || !Object.keys(rig.states).length || Object.keys(rig.states).length > 128) fail('1..128 named states required');
  for (const [name, state] of Object.entries(rig.states)) {
    if (!validName(name) || !object(state) || typeof state.source !== 'string' || !state.source.trim() || !Array.isArray(state.sequence) || !state.sequence.length || state.sequence.length > 4096) fail(`${name}: state needs source and sequence`);
    let total = 0;
    for (const step of state.sequence) {
      if (!object(step) || !Object.hasOwn(frames, step.frame) || !Number.isSafeInteger(step.ticks) || step.ticks <= 0) fail(`${name}: unknown frame or invalid ticks`);
      total += step.ticks;
    }
    if (total > 36000) fail(`${name}: sequence exceeds 36000 ticks; describe conditional holds in notes`);
  }
  if (!object(rig.reference) || typeof rig.reference.name !== 'string' || typeof rig.reference.source !== 'string') fail('native-size reference with source required');
  indexed(rig.reference, 'reference');
  if (rig.reference.feet !== undefined) point(rig.reference.feet, 'reference.feet', rig.reference.width, rig.reference.height);
  return { ...structuredClone(rig), frames };
}
function renderRigArtifacts(result) {
  if (!result.rig) return {};
  const artifacts = {}, rig = result.rig;
  for (const [stateName, state] of Object.entries(rig.states)) {
    for (const scale of [1, 4]) {
      const referenceFeet = rig.reference.feet ?? [Math.floor(rig.reference.width / 2), rig.reference.height - 1];
      const top = Math.max(referenceFeet[1], ...state.sequence.map(step => rig.frames[step.frame].feet?.[1] ?? result.height - 1));
      const bottom = Math.max(rig.reference.height - referenceFeet[1], ...state.sequence.map(step => result.height - (rig.frames[step.frame].feet?.[1] ?? result.height - 1)));
      const cw = Math.max(300, (result.width + rig.reference.width + 20) * scale + 24), ch = (top + bottom) * scale + 84;
      const cols = Math.min(4, state.sequence.length), sheet = canvas(cols * cw, Math.ceil(state.sequence.length / cols) * ch, [24, 26, 35]);
      state.sequence.forEach((step, i) => {
        const frame = rig.frames[step.frame], x = i % cols * cw + 12, y = Math.floor(i / cols) * ch + 10;
        text(sheet, step.frame, x, y, 1, cw - 24);
        text(sheet, `${step.ticks} TICKS`, x, y + 12, 1, cw - 24);
        if (frame.alias_of) text(sheet, `ALIAS ${frame.alias_of}`, x, y + 24, 1, cw - 24);
        const baseline = y + 42 + top * scale;
        sprite(sheet, result, frame.pixels, x, baseline - (frame.feet?.[1] ?? result.height - 1) * scale, scale);
        sprite(sheet, rig.reference, rig.reference.pixels, x + (result.width + 12) * scale, baseline - referenceFeet[1] * scale, scale);
        text(sheet, rig.reference.name, x + (result.width + 12) * scale, baseline + bottom * scale + 5, 1, cw - (result.width + 12) * scale - 12);
        // GIF frames share labels, dimensions and the native reference.
        if (scale === 4) {
          const image = canvas(cw, ch, [24, 26, 35]);
          for (let yy = 0; yy < ch; yy++) sheet.rgba.copy(image.rgba, yy * cw * 4, ((Math.floor(i / cols) * ch + yy) * sheet.width + i % cols * cw) * 4, ((Math.floor(i / cols) * ch + yy) * sheet.width + i % cols * cw + cw) * 4);
          artifacts[`state-${stateName}-${i}.png`] = png(image);
        }
      });
      artifacts[`state-${stateName}-${scale}x.png`] = png(sheet);
    }
  }
  return artifacts;
}
function writeRigGifs(result, outputPath) {
  for (const [name, state] of Object.entries(result.rig?.states ?? {})) {
    let concat = state.sequence.map((step, i) => `file state-${name}-${i}.png\noption framerate ${result.tickRate}\nduration ${step.ticks / result.tickRate}\n`).join('');
    concat += `file state-${name}-${state.sequence.length - 1}.png\noption framerate ${result.tickRate}\n`;
    fs.writeFileSync(path.join(outputPath, `state-${name}.ffconcat`), concat, { flag: 'wx' });
    const ticks = state.sequence.reduce((n, step) => n + step.ticks, 0);
    const encoded = spawnSync('ffmpeg', ['-nostdin', '-n', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', `state-${name}.ffconcat`, '-filter_complex', `fps=${result.tickRate},split[a][b];[a]palettegen[p];[b][p]paletteuse=dither=none`, '-frames:v', String(ticks), '-loop', '0', `state-${name}.gif`], { cwd: outputPath, encoding: 'utf8' });
    if (encoded.status !== 0) fail(`ffmpeg failed: ${encoded.stderr || encoded.error?.message}`);
  }
}
module.exports = { evaluateRig, renderRigArtifacts, writeRigGifs };
