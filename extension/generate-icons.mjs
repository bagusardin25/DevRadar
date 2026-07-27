import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { deflateSync } from 'zlib';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const outDir = resolve(__dirname, 'public/icons');
if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });

function crc32(buf) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < buf.length; i++) {
    crc ^= buf[i];
    for (let j = 0; j < 8; j++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xEDB88320 : 0);
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const typeAndData = Buffer.concat([Buffer.from(type), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(typeAndData));
  return Buffer.concat([len, typeAndData, crc]);
}

function createPNG(size) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // RGBA
  ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;

  // Draw a radar icon: rounded orange square with white "D" shape
  const raw = Buffer.alloc(size * (size * 4 + 1));
  const cx = size / 2, cy = size / 2;
  const r = size * 0.42; // main radius
  const cornerR = size * 0.18; // corner radius for rounded rect

  for (let y = 0; y < size; y++) {
    const rowStart = y * (size * 4 + 1);
    raw[rowStart] = 0; // filter none
    for (let x = 0; x < size; x++) {
      const px = rowStart + 1 + x * 4;
      const dx = x - cx, dy = y - cy;
      const dist = Math.sqrt(dx * dx + dy * dy);

      // Rounded rectangle background
      const inset = size * 0.08;
      const rx = Math.abs(x - cx) - (cx - inset - cornerR);
      const ry = Math.abs(y - cy) - (cy - inset - cornerR);
      const cornerDist = rx > 0 && ry > 0 ? Math.sqrt(rx * rx + ry * ry) : Math.max(rx, ry);
      const inRoundedRect = cornerDist <= cornerR;

      if (!inRoundedRect) {
        raw[px] = 0; raw[px + 1] = 0; raw[px + 2] = 0; raw[px + 3] = 0;
        continue;
      }

      // Orange background (#FF5A36)
      let R = 255, G = 90, B = 54, A = 255;

      // Draw radar arcs (white, semi-transparent)
      const angle = Math.atan2(-dy, dx);
      const inUpperRight = angle >= -Math.PI / 2 && angle <= Math.PI / 2 && dy <= 0;

      // Arc rings
      for (const arcR of [r * 0.35, r * 0.6, r * 0.85]) {
        if (Math.abs(dist - arcR) < size * 0.025 && inUpperRight) {
          R = 255; G = 255; B = 255; A = 220;
        }
      }

      // Radar sweep line (diagonal)
      const sweepAngle = Math.PI * 0.25; // 45 degrees
      const angleDiff = Math.abs(angle - sweepAngle);
      if (angleDiff < 0.04 && dist < r && dist > size * 0.04) {
        R = 255; G = 255; B = 255; A = 240;
      }

      // Center dot
      if (dist < size * 0.06) {
        R = 255; G = 255; B = 255; A = 255;
      }

      // Blip dot
      const blipX = cx + r * 0.5 * Math.cos(Math.PI * 0.35);
      const blipY = cy - r * 0.5 * Math.sin(Math.PI * 0.35);
      const blipDist = Math.sqrt((x - blipX) ** 2 + (y - blipY) ** 2);
      if (blipDist < size * 0.055) {
        R = 255; G = 255; B = 255; A = 255;
      }

      raw[px] = R; raw[px + 1] = G; raw[px + 2] = B; raw[px + 3] = A;
    }
  }

  const compressed = deflateSync(raw);
  const ihdrChunk = chunk('IHDR', ihdr);
  const idatChunk = chunk('IDAT', compressed);
  const iendChunk = chunk('IEND', Buffer.alloc(0));

  return Buffer.concat([sig, ihdrChunk, idatChunk, iendChunk]);
}

for (const size of [16, 48, 128]) {
  const png = createPNG(size);
  const path = resolve(outDir, `icon-${size}.png`);
  writeFileSync(path, png);
  console.log(`Generated ${path} (${png.length} bytes)`);
}
