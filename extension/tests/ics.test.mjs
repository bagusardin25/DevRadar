import assert from 'node:assert/strict';
import test from 'node:test';

import { generateICS } from '../src/shared/ics.ts';

test('generateICS keeps untrusted titles inside SUMMARY', () => {
  for (const lineBreak of ['\r\n', '\n', '\r']) {
    const maliciousTitle = [
      'Cool Hack',
      'ORGANIZER;CN=Attacker:mailto:evil@attacker.com',
      'ATTENDEE;RSVP=TRUE:mailto:victim@corp.com',
    ].join(lineBreak);

    const ics = generateICS(maliciousTitle, '2026-08-01T00:00:00.000Z');
    const lines = ics.split('\r\n');

    assert.equal(lines.filter((line) => line.startsWith('SUMMARY:')).length, 1);
    assert.equal(lines.some((line) => line.startsWith('ORGANIZER')), false);
    assert.equal(lines.some((line) => line.startsWith('ATTENDEE')), false);
    assert.ok(ics.includes(
      'SUMMARY:Cool Hack\\nORGANIZER\\;CN=Attacker:mailto:evil@attacker.com' +
      '\\nATTENDEE\\;RSVP=TRUE:mailto:victim@corp.com',
    ));
  }
});

test('generateICS preserves legitimate text using RFC 5545 escaping', () => {
  const ics = generateICS('R&D, APIs; C:\\Projects', '2026-08-01T00:00:00.000Z');

  assert.ok(ics.includes('DTSTART:20260801T000000Z'));
  assert.ok(ics.includes('DTEND:20260801T010000Z'));
  assert.ok(ics.includes('SUMMARY:R&D\\, APIs\\; C:\\\\Projects'));
});
