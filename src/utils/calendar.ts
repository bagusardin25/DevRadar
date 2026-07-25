/**
 * Calendar utilities for hackathon deadline export (Wave D — D3 & D4).
 *
 * Pure client-side: no backend dependency.
 *  – D3: `.ics` blob download  (iCalendar RFC 5545)
 *  – D4: Google Calendar URL builder
 */

/** Strip non-alphanumeric for UID generation. */
function sanitiseUID(id: string): string {
  return id.replace(/[^a-zA-Z0-9-]/g, '');
}

/** Format a Date to iCalendar DTSTART/DTEND format: `YYYYMMDDTHHmmSSZ` */
function toICSDate(date: Date): string {
  return date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
}

/** Format a Date for Google Calendar URL: `YYYYMMDDTHHmmSSZ` (same as ICS). */
function toGCalDate(date: Date): string {
  return toICSDate(date);
}

/** Escape special characters for iCalendar text fields. */
function escapeICS(text: string): string {
  return text
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\n/g, '\\n');
}

export interface CalendarEvent {
  /** Unique item ID (e.g. hackathon.id). */
  id: string;
  /** Event summary / title. */
  title: string;
  /** ISO date string for event start. */
  startDate: string;
  /** ISO date string for event end (defaults to start + 1h). */
  endDate?: string;
  /** Plain-text description. */
  description?: string;
  /** Location string (URL or physical). */
  location?: string;
  /** Official URL for the event. */
  url?: string;
}

// ───────────────────────────────────────────────
// D3 — .ics download
// ───────────────────────────────────────────────

/**
 * Generate an iCalendar (.ics) string for one or more events.
 */
export function generateICS(events: CalendarEvent[]): string {
  const lines: string[] = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//DevRadar//Hackathon Deadline//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
  ];

  for (const evt of events) {
    const start = new Date(evt.startDate);
    const end = evt.endDate
      ? new Date(evt.endDate)
      : new Date(start.getTime() + 60 * 60 * 1000); // +1h default

    // 30-minute reminder alarm
    const alarm = [
      'BEGIN:VALARM',
      'TRIGGER:-PT30M',
      'ACTION:DISPLAY',
      `DESCRIPTION:Reminder: ${escapeICS(evt.title)}`,
      'END:VALARM',
    ];

    const desc = evt.description
      ? `DESCRIPTION:${escapeICS(evt.description)}${evt.url ? `\\n\\nMore info: ${evt.url}` : ''}`
      : evt.url
        ? `DESCRIPTION:More info: ${evt.url}`
        : '';

    lines.push(
      'BEGIN:VEVENT',
      `UID:${sanitiseUID(evt.id)}@devradar`,
      `DTSTAMP:${toICSDate(new Date())}`,
      `DTSTART:${toICSDate(start)}`,
      `DTEND:${toICSDate(end)}`,
      `SUMMARY:${escapeICS(evt.title)}`,
      ...(desc ? [desc] : []),
      ...(evt.location ? [`LOCATION:${escapeICS(evt.location)}`] : []),
      ...(evt.url ? [`URL:${evt.url}`] : []),
      ...alarm,
      'END:VEVENT',
    );
  }

  lines.push('END:VCALENDAR');
  return lines.join('\r\n');
}

/**
 * Trigger a `.ics` file download in the browser.
 */
export function downloadICS(events: CalendarEvent[], filename = 'devradar-deadline.ics'): void {
  const icsContent = generateICS(events);
  const blob = new Blob([icsContent], { type: 'text/calendar;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// ───────────────────────────────────────────────
// D4 — Google Calendar URL
// ───────────────────────────────────────────────

/**
 * Build a Google Calendar "Add Event" URL.
 */
export function buildGoogleCalendarUrl(event: CalendarEvent): string {
  const start = new Date(event.startDate);
  const end = event.endDate
    ? new Date(event.endDate)
    : new Date(start.getTime() + 60 * 60 * 1000);

  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: event.title,
    dates: `${toGCalDate(start)}/${toGCalDate(end)}`,
    ...(event.description && { details: event.description + (event.url ? `\n\nMore info: ${event.url}` : '') }),
    ...(event.location && { location: event.location }),
    ...(event.url && { sprop: `website:${event.url}` }),
  });

  return `https://www.google.com/calendar/render?${params.toString()}`;
}

// ───────────────────────────────────────────────
// Helpers — build CalendarEvent from hackathon data
// ───────────────────────────────────────────────

export interface HackathonCalendarInput {
  id: string;
  title: string;
  organizer: string;
  registrationDeadline: string;
  submissionDeadline: string;
  officialUrl: string;
  mode: string;
  location?: string;
}

/**
 * Create a CalendarEvent for the **registration deadline**.
 */
export function hackathonRegDeadlineEvent(h: HackathonCalendarInput): CalendarEvent {
  return {
    id: `${h.id}-reg`,
    title: `📋 Reg deadline: ${h.title}`,
    startDate: h.registrationDeadline,
    description: `Registration closes for "${h.title}" by ${h.organizer}.\nMode: ${h.mode}`,
    location: h.location || h.officialUrl,
    url: h.officialUrl,
  };
}

/**
 * Create a CalendarEvent for the **submission deadline**.
 */
export function hackathonSubDeadlineEvent(h: HackathonCalendarInput): CalendarEvent {
  return {
    id: `${h.id}-sub`,
    title: `🚀 Submission due: ${h.title}`,
    startDate: h.submissionDeadline,
    description: `Submission deadline for "${h.title}" by ${h.organizer}.\nMode: ${h.mode}`,
    location: h.location || h.officialUrl,
    url: h.officialUrl,
  };
}
