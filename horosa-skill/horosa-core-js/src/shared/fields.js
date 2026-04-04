function ensureDateString(value) {
  const text = `${value || ''}`.trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    throw new Error(`Invalid date string: ${text || '<empty>'}`);
  }
  return text;
}

function ensureTimeString(value) {
  const text = `${value || ''}`.trim();
  if (/^\d{2}:\d{2}$/.test(text)) {
    return `${text}:00`;
  }
  if (!/^\d{2}:\d{2}:\d{2}$/.test(text)) {
    throw new Error(`Invalid time string: ${text || '<empty>'}`);
  }
  return text;
}

function buildFormatter(dateText, timeText) {
  const [year, month, day] = dateText.split('-');
  const [hour, minute, second] = timeText.split(':');
  return {
    format(pattern) {
      switch (pattern) {
        case 'YYYY-MM-DD':
          return dateText;
        case 'YYYY':
          return year;
        case 'MM':
          return month;
        case 'DD':
          return day;
        case 'HH:mm':
          return `${hour}:${minute}`;
        case 'HH:mm:ss':
          return timeText;
        case 'HH':
          return hour;
        default:
          throw new Error(`Unsupported format pattern: ${pattern}`);
      }
    },
  };
}

export function normalizeDateTimeInput(payload) {
  return {
    ...payload,
    date: ensureDateString(payload.date),
    time: ensureTimeString(payload.time),
  };
}

export function makeFields(payload) {
  const normalized = normalizeDateTimeInput(payload);
  const dateValue = buildFormatter(normalized.date, normalized.time);
  const timeValue = buildFormatter(normalized.date, normalized.time);
  return {
    date: { value: dateValue },
    time: { value: timeValue },
    zone: { value: normalized.zone ?? '+08:00' },
    lon: { value: normalized.lon ?? '' },
    lat: { value: normalized.lat ?? '' },
    gpsLat: { value: normalized.gpsLat ?? null },
    gpsLon: { value: normalized.gpsLon ?? null },
    ad: { value: normalized.ad ?? 1 },
    after23NewDay: { value: normalized.after23NewDay ?? 0 },
  };
}
