import { parseDateParts } from '../vendor/bazi/dateStrSafe.js';

// 年带符号、4–5 位（formatSignedDate 同形：公元前 '-0500-03-21'、五位年 '10000-01-01'；Python 侧 input_normalization
// 归一成这个形状）。旧式只认 `\d{4}` → 公元前 / 五位年的奇门 / 太乙 / 三式合一一律抛 Invalid date string。
function ensureDateString(value) {
  const text = `${value || ''}`.trim();
  if (!/^-?\d{4,5}-\d{2}-\d{2}$/.test(text) || !parseDateParts(text)) {
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

// 上游 comp/DateTime.format 的子集：年 = ad × year（带符号整数、不补零——公元前 '-500'，公元 999 年 '999'），
// 'YYYY-MM-DD' = `${ad × year}-MM-DD`。旧式 dateText.split('-') 对公元前撕成 ['', '0500', …]：'YYYY' 得 ''、
// 'YYYY-MM-DD' 原样回带补零的串。日期不带负号而 ad=-1（公元前的另一种写法）同样读成负年。
function dateTimeYmd(dateText, ad) {
  const parts = parseDateParts(dateText);
  if (!parts) {
    return null;
  }
  const signedYear = parts.year > 0 && Number(ad) === -1 ? -parts.year : parts.year;
  return { year: `${signedYear}`, month: String(parts.month).padStart(2, '0'), day: String(parts.day).padStart(2, '0') };
}

/** DateTime.format('YYYY-MM-DD') 同形（'-500-03-21' / '999-01-02'）；认不出原样返回。 */
export function formatDateLikeDateTime(dateText, ad) {
  const ymd = dateTimeYmd(dateText, ad);
  return ymd ? `${ymd.year}-${ymd.month}-${ymd.day}` : `${dateText ?? ''}`;
}

function buildFormatter(dateText, timeText, ad) {
  const { year, month, day } = dateTimeYmd(dateText, ad);
  const [hour, minute, second] = timeText.split(':');
  return {
    format(pattern) {
      switch (pattern) {
        case 'YYYY-MM-DD':
          return `${year}-${month}-${day}`;
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
  const dateValue = buildFormatter(normalized.date, normalized.time, normalized.ad);
  const timeValue = buildFormatter(normalized.date, normalized.time, normalized.ad);
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
