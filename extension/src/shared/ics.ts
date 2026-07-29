export function escapeICalText(value: string): string {
  return value
    .replace(/\\/g, '\\\\')
    .replace(/\r\n|\r|\n/g, '\\n')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,');
}

export function generateICS(title: string, dateStr: string): string {
  const start = new Date(dateStr);
  const formatDate = (date: Date) => date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
  const end = new Date(start.getTime() + 3600000);

  return [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//DevRadar//EN',
    'BEGIN:VEVENT',
    `DTSTART:${formatDate(start)}`,
    `DTEND:${formatDate(end)}`,
    `SUMMARY:${escapeICalText(title)}`,
    'END:VEVENT',
    'END:VCALENDAR',
  ].join('\r\n');
}
