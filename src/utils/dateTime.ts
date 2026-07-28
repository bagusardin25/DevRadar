export const APP_LOCALE = 'en-US';

export function formatAppDateTime(
  value: string | number | Date,
  options: Intl.DateTimeFormatOptions,
  fallback = 'Unknown',
): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return new Intl.DateTimeFormat(APP_LOCALE, options).format(date);
}

export function formatAppDate(
  value: string | number | Date,
  options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  },
  fallback = 'Unknown',
): string {
  return formatAppDateTime(value, options, fallback);
}
