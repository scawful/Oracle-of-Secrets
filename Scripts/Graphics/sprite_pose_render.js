'use strict';

// Small stdlib renderer for integer palette pixels. No source-file imports.
const zlib = require('node:zlib');
const crcTable = Array.from({ length: 256 }, (_, n) => {
  for (let bit = 0; bit < 8; bit++) n = n & 1 ? 0xedb88320 ^ (n >>> 1) : n >>> 1;
  return n >>> 0;
});
function crc(buffer) {
  let value = 0xffffffff;
  for (const byte of buffer) value = crcTable[(value ^ byte) & 255] ^ (value >>> 8);
  return (value ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const name = Buffer.from(type), size = Buffer.alloc(4), checksum = Buffer.alloc(4);
  size.writeUInt32BE(data.length);
  checksum.writeUInt32BE(crc(Buffer.concat([name, data])));
  return Buffer.concat([size, name, data, checksum]);
}
function encodePng(width, height, rgba) {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width); header.writeUInt32BE(height, 4); header[8] = 8; header[9] = 6;
  const rows = Buffer.alloc(height * (width * 4 + 1));
  for (let y = 0; y < height; y++) rgba.copy(rows, y * (width * 4 + 1) + 1, y * width * 4, (y + 1) * width * 4);
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', header), chunk('IDAT', zlib.deflateSync(rows)), chunk('IEND', Buffer.alloc(0))]);
}
function canvas(width, height, background) {
  if (!Number.isSafeInteger(width * height) || width <= 0 || height <= 0 || width * height > 16777216) throw new Error('Rendered canvas exceeds 16777216 pixels; reduce --scale or split the recipe');
  const image = { width, height, rgba: Buffer.alloc(width * height * 4) };
  if (background) rect(image, 0, 0, width, height, background);
  return image;
}
function rect(image, x, y, width, height, color) {
  for (let yy = Math.max(0, y); yy < Math.min(image.height, y + height); yy++) {
    for (let xx = Math.max(0, x); xx < Math.min(image.width, x + width); xx++) {
      const offset = (yy * image.width + xx) * 4;
      image.rgba[offset] = color[0]; image.rgba[offset + 1] = color[1]; image.rgba[offset + 2] = color[2]; image.rgba[offset + 3] = color[3] ?? 255;
    }
  }
}
const FONT = {
  A:['01110','10001','10001','11111','10001','10001','10001'], B:['11110','10001','10001','11110','10001','10001','11110'], C:['01111','10000','10000','10000','10000','10000','01111'], D:['11110','10001','10001','10001','10001','10001','11110'], E:['11111','10000','10000','11110','10000','10000','11111'], F:['11111','10000','10000','11110','10000','10000','10000'], G:['01111','10000','10000','10111','10001','10001','01110'], H:['10001','10001','10001','11111','10001','10001','10001'], I:['111','010','010','010','010','010','111'], J:['00111','00010','00010','00010','10010','10010','01100'], K:['10001','10010','10100','11000','10100','10010','10001'], L:['10000','10000','10000','10000','10000','10000','11111'], M:['10001','11011','10101','10101','10001','10001','10001'], N:['10001','11001','10101','10011','10001','10001','10001'], O:['01110','10001','10001','10001','10001','10001','01110'], P:['11110','10001','10001','11110','10000','10000','10000'], Q:['01110','10001','10001','10001','10101','10010','01101'], R:['11110','10001','10001','11110','10100','10010','10001'], S:['01111','10000','10000','01110','00001','00001','11110'], T:['11111','00100','00100','00100','00100','00100','00100'], U:['10001','10001','10001','10001','10001','10001','01110'], V:['10001','10001','10001','10001','10001','01010','00100'], W:['10001','10001','10001','10101','10101','10101','01010'], X:['10001','10001','01010','00100','01010','10001','10001'], Y:['10001','10001','01010','00100','00100','00100','00100'], Z:['11111','00001','00010','00100','01000','10000','11111'],
  0:['01110','10001','10011','10101','11001','10001','01110'], 1:['010','110','010','010','010','010','111'], 2:['01110','10001','00001','00010','00100','01000','11111'], 3:['11110','00001','00001','01110','00001','00001','11110'], 4:['00010','00110','01010','10010','11111','00010','00010'], 5:['11111','10000','10000','11110','00001','00001','11110'], 6:['01110','10000','10000','11110','10001','10001','01110'], 7:['11111','00001','00010','00100','01000','01000','01000'], 8:['01110','10001','10001','01110','10001','10001','01110'], 9:['01110','10001','10001','01111','00001','00001','01110'], '-':['00000','00000','00000','11111','00000','00000','00000']
};
function text(image, value, x, y, scale = 2, maxWidth = image.width - x) {
  const start = x;
  for (const character of String(value).toUpperCase().replaceAll('_', ' ')) {
    const glyph = FONT[character];
    const advance = glyph ? (glyph[0].length + 1) * scale : 4 * scale;
    if (x + advance - start > maxWidth) break;
    if (glyph) for (let yy = 0; yy < 7; yy++) for (let xx = 0; xx < glyph[yy].length; xx++) {
      if (glyph[yy][xx] === '1') rect(image, x + xx * scale, y + yy * scale, scale, scale, [220, 220, 230]);
    }
    x += advance;
  }
}
function sprite(image, result, pixels, x, y, scale, gray = false) {
  for (let yy = 0; yy < result.height; yy++) for (let xx = 0; xx < result.width; xx++) {
    const index = pixels[yy * result.width + xx];
    if (index !== result.transparentIndex) rect(image, x + xx * scale, y + yy * scale, scale, scale, gray ? [56, 57, 64] : result.palette[index]);
  }
}
const png = image => encodePng(image.width, image.height, image.rgba);

function renderArtifacts(result, scale = 8) {
  if (!Number.isInteger(scale) || scale < 1 || scale > 32) throw new Error('Render scale must be an integer from 1 to 32');
  const artifacts = {};
  const source = canvas(result.width * scale, result.height * scale);
  sprite(source, result, result.sourcePixels, 0, 0, scale);
  artifacts['source.png'] = png(source);
  const names = Object.keys(result.frames), columns = Math.min(4, names.length);
  const cellWidth = Math.max(result.width * scale + 32, 260), cellHeight = result.height * scale + 64;
  const contact = canvas(columns * cellWidth, Math.ceil(names.length / columns) * cellHeight, [24, 26, 35]);
  names.forEach((name, index) => {
    const frame = result.frames[name], image = canvas(result.width * scale, result.height * scale);
    sprite(image, result, frame.pixels, 0, 0, scale);
    artifacts[`pose-${name}.png`] = png(image);
    const x = (index % columns) * cellWidth + 16, y = Math.floor(index / columns) * cellHeight + 12;
    text(contact, name, x, y, 2, cellWidth - 32);
    sprite(contact, result, frame.pixels, x, y + 30, scale);
  });
  artifacts['contact.png'] = png(contact);
  const atlasScale = Math.min(scale, 4), atlasColumns = Math.min(5, result.segments.length);
  const atlasCellWidth = Math.max(result.width * atlasScale + 32, 260), atlasCellHeight = result.height * atlasScale + 96;
  const atlas = canvas(atlasColumns * atlasCellWidth, Math.ceil(result.segments.length / atlasColumns) * atlasCellHeight, [24, 26, 35]);
  result.segments.forEach((segment, index) => {
    const x = (index % atlasColumns) * atlasCellWidth + 16, y = Math.floor(index / atlasColumns) * atlasCellHeight + 12;
    text(atlas, segment.label ?? segment.id, x, y, 2, atlasCellWidth - 32);
    sprite(atlas, result, result.sourcePixels, x, y + 28, atlasScale, true);
    for (const [px, py, color] of segment.pixels) rect(atlas, x + px * atlasScale, y + 28 + py * atlasScale, atlasScale, atlasScale, result.palette[color]);
    const [sx, sy, width, height] = segment.rect, left = x + sx * atlasScale, top = y + 28 + sy * atlasScale;
    rect(atlas, left, top, width * atlasScale, 1, [64, 200, 220]);
    rect(atlas, left, top + height * atlasScale - 1, width * atlasScale, 1, [64, 200, 220]);
    rect(atlas, left, top, 1, height * atlasScale, [64, 200, 220]);
    rect(atlas, left + width * atlasScale - 1, top, 1, height * atlasScale, [64, 200, 220]);
    text(atlas, segment.rect.join(' '), x, y + 40 + result.height * atlasScale, 2, atlasCellWidth - 32);
    text(atlas, `${segment.pixels.length} PIXELS`, x, y + 60 + result.height * atlasScale, 2, atlasCellWidth - 32);
  });
  artifacts['atlas.png'] = png(atlas);
  return artifacts;
}

module.exports = { renderArtifacts, encodePng };
