/* ============================================================================
 *  Bop Social — Internationalization & Locale Formatting Utilities
 *  Provides locale-aware date, time, relative time, number, and currency
 *  formatting, strictly decoupling language from currency values.
 * ========================================================================== */
import i18n from '../i18n/config';

/**
 * Resolve active locale string for Intl APIs ('en-US' or 'es-ES')
 * @param {string} [overrideLocale]
 * @returns {string}
 */
export function getResolvedLocale(overrideLocale) {
  const lang = overrideLocale || (i18n && i18n.language) || 'en';
  if (lang.startsWith('es')) return 'es-ES';
  return 'en-US';
}

/**
 * Safely parse date representations avoiding UTC offset shifts on YYYY-MM-DD strings.
 * @param {Date|string|number} val
 * @returns {Date|null}
 */
export function parseDateSafe(val) {
  if (!val) return null;
  if (val instanceof Date) return isNaN(val.getTime()) ? null : val;
  if (typeof val === 'string') {
    const trimmed = val.trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
      const [y, m, d] = trimmed.split('-').map(Number);
      return new Date(y, m - 1, d);
    }
  }
  const d = new Date(val);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Format date in locale-aware format
 * @param {Date|string|number} date
 * @param {Intl.DateTimeFormatOptions} [options]
 * @param {string} [locale]
 * @returns {string}
 */
export function formatDate(date, options = { dateStyle: 'medium' }, locale) {
  const d = parseDateSafe(date);
  if (!d) return '';
  const resolved = getResolvedLocale(locale);
  return new Intl.DateTimeFormat(resolved, options).format(d);
}

/**
 * Format month and year with proper title casing for the leading month only
 * (e.g. "September 2026" in English, "Septiembre de 2026" in Spanish - avoids "Septiembre De 2026")
 * @param {Date|string|number} date
 * @param {string} [locale]
 * @returns {string}
 */
export function formatMonthYear(date, locale) {
  const d = parseDateSafe(date);
  if (!d) return '';
  const resolved = getResolvedLocale(locale);
  const formatted = new Intl.DateTimeFormat(resolved, { month: 'long', year: 'numeric' }).format(d);
  if (!formatted) return '';
  return formatted.charAt(0).toUpperCase() + formatted.slice(1);
}

/**
 * Format a month number (1-12) to its localized full month name.
 * (e.g. 9 in 'es' -> "septiembre", 9 in 'en' -> "September")
 * @param {number|string} monthNumber - 1 to 12
 * @param {string} [locale]
 * @returns {string}
 */
export function formatMonthName(monthNumber, locale) {
  const num = parseInt(monthNumber, 10);
  if (isNaN(num) || num < 1 || num > 12) return '';
  const d = new Date(2026, num - 1, 15);
  const resolved = getResolvedLocale(locale);
  return new Intl.DateTimeFormat(resolved, { month: 'long' }).format(d);
}

/**
 * Format date range in a locale-aware format
 * @param {Date|string|number} startDate
 * @param {Date|string|number} endDate
 * @param {Intl.DateTimeFormatOptions} [options]
 * @param {string} [locale]
 * @returns {string}
 */
export function formatDateRange(startDate, endDate, options = { dateStyle: 'medium' }, locale) {
  if (!startDate && !endDate) return '';
  if (!startDate) return formatDate(endDate, options, locale);
  if (!endDate) return formatDate(startDate, options, locale);

  const d1 = parseDateSafe(startDate);
  const d2 = parseDateSafe(endDate);
  if (!d1 || !d2) return `${startDate} – ${endDate}`;

  const resolved = getResolvedLocale(locale);
  try {
    const dtf = new Intl.DateTimeFormat(resolved, options);
    if (typeof dtf.formatRange === 'function') {
      return dtf.formatRange(d1, d2);
    }
    const sep = resolved.startsWith('es') ? ' al ' : ' to ';
    return `${dtf.format(d1)}${sep}${dtf.format(d2)}`;
  } catch (err) {
    const sep = resolved.startsWith('es') ? ' al ' : ' to ';
    return `${formatDate(d1, options, locale)}${sep}${formatDate(d2, options, locale)}`;
  }
}

/**
 * Format time in locale-aware format
 * @param {Date|string|number} date
 * @param {Intl.DateTimeFormatOptions} [options]
 * @param {string} [locale]
 * @returns {string}
 */
export function formatTime(date, options = { timeStyle: 'short' }, locale) {
  if (!date) return '';
  const d = new Date(date);
  if (isNaN(d.getTime())) return '';
  const resolved = getResolvedLocale(locale);
  return new Intl.DateTimeFormat(resolved, options).format(d);
}

/**
 * Format relative time (e.g. "3 hours ago", "hace 3 horas", "in 2 days", "en 2 días")
 * @param {Date|string|number} date
 * @param {string} [locale]
 * @returns {string}
 */
export function formatRelativeTime(date, locale) {
  if (!date) return '';
  const d = new Date(date);
  if (isNaN(d.getTime())) return '';

  const now = new Date();
  const elapsedSeconds = Math.round((d.getTime() - now.getTime()) / 1000);
  const resolved = getResolvedLocale(locale);

  if (typeof Intl.RelativeTimeFormat === 'function') {
    const rtf = new Intl.RelativeTimeFormat(resolved, { numeric: 'auto' });
    const absSeconds = Math.abs(elapsedSeconds);

    if (absSeconds < 60) {
      return rtf.format(elapsedSeconds, 'second');
    }
    const elapsedMinutes = Math.round(elapsedSeconds / 60);
    if (Math.abs(elapsedMinutes) < 60) {
      return rtf.format(elapsedMinutes, 'minute');
    }
    const elapsedHours = Math.round(elapsedMinutes / 60);
    if (Math.abs(elapsedHours) < 24) {
      return rtf.format(elapsedHours, 'hour');
    }
    const elapsedDays = Math.round(elapsedHours / 24);
    if (Math.abs(elapsedDays) < 30) {
      return rtf.format(elapsedDays, 'day');
    }
    const elapsedMonths = Math.round(elapsedDays / 30);
    if (Math.abs(elapsedMonths) < 12) {
      return rtf.format(elapsedMonths, 'month');
    }
    const elapsedYears = Math.round(elapsedDays / 365);
    return rtf.format(elapsedYears, 'year');
  }

  // Fallback if RelativeTimeFormat is missing
  return formatDate(d, { dateStyle: 'short' }, locale);
}

/**
 * Format standard number with locale-aware thousands and decimal separators
 * @param {number} value
 * @param {Intl.NumberFormatOptions} [options]
 * @param {string} [locale]
 * @returns {string}
 */
export function formatNumber(value, options = {}, locale) {
  if (value === null || value === undefined || isNaN(Number(value))) return '0';
  const resolved = getResolvedLocale(locale);
  return new Intl.NumberFormat(resolved, options).format(Number(value));
}

/**
 * Format percentage (e.g. 0.25 -> 25% or 25,0 %)
 * @param {number} value - Decimal value (e.g. 0.125 for 12.5%)
 * @param {number} [digits=1]
 * @param {string} [locale]
 * @returns {string}
 */
export function formatPercent(value, digits = 1, locale) {
  if (value === null || value === undefined || isNaN(Number(value))) return '0%';
  const resolved = getResolvedLocale(locale);
  return new Intl.NumberFormat(resolved, {
    style: 'percent',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number(value));
}

/**
 * Format currency strictly decoupled from language locale
 * e.g. formatCurrency(1250, 'USD', 'es') -> "1250,00 US$"
 * e.g. formatCurrency(1250, 'EUR', 'en') -> "€1,250.00"
 * @param {number|null|undefined} value
 * @param {string} [currencyCode='USD']
 * @param {string} [locale]
 * @param {object} [options]
 * @returns {string}
 */
export function formatCurrency(value, currencyCode = 'USD', locale, options = {}) {
  const code = (currencyCode || 'USD').toUpperCase();
  const resolved = getResolvedLocale(locale);
  if (value === null || value === undefined || isNaN(Number(value))) {
    if (code === 'USD' && resolved.startsWith('en')) {
      return '$0.00';
    }
    try {
      return new Intl.NumberFormat(resolved, {
        style: 'currency',
        currency: code,
        ...options,
      }).format(0);
    } catch {
      return `${code} 0`;
    }
  }
  try {
    return new Intl.NumberFormat(resolved, {
      style: 'currency',
      currency: code,
      ...options,
    }).format(Number(value));
  } catch (err) {
    // If currencyCode is unrecognized, format as generic number with code prefix
    return `${code} ${formatNumber(value, { minimumFractionDigits: 0, maximumFractionDigits: 2 }, locale)}`;
  }
}

/**
 * Format compact currency strictly decoupled from language locale
 * e.g. formatCompactCurrency(1250000, 'USD', 'en') -> "$1.3M"
 * @param {number|null|undefined} value
 * @param {string} [currencyCode='USD']
 * @param {string} [locale]
 * @param {object} [options]
 * @returns {string}
 */
export function formatCompactCurrency(value, currencyCode = 'USD', locale, options = {}) {
  if (value === null || value === undefined || isNaN(Number(value))) return '—';
  const code = (currencyCode || 'USD').toUpperCase();
  const resolved = getResolvedLocale(locale);
  try {
    return new Intl.NumberFormat(resolved, {
      style: 'currency',
      currency: code,
      notation: 'compact',
      ...options,
    }).format(Number(value));
  } catch (err) {
    return `${code} ${formatCompactNumber(Number(value), 1, locale)}`;
  }
}
