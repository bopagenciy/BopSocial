import {
  formatDate,
  formatDateRange,
  formatTime,
  formatRelativeTime,
  formatNumber,
  formatPercent,
  formatCurrency,
  formatCompactCurrency,
  getResolvedLocale,
  parseDateSafe,
} from '../formatters';

describe('Bop Social Locale Formatting Utilities Suite', () => {
  const testDate = new Date('2026-06-15T14:30:00Z');

  test('resolves correct locale identifiers for en and es', () => {
    expect(getResolvedLocale('en')).toBe('en-US');
    expect(getResolvedLocale('es')).toBe('es-ES');
  });

  test('formats dates in English and Spanish', () => {
    const enDate = formatDate(testDate, { dateStyle: 'medium' }, 'en');
    const esDate = formatDate(testDate, { dateStyle: 'medium' }, 'es');

    expect(enDate).toContain('2026');
    expect(esDate).toContain('2026');
    // English includes Jun / June, Spanish includes jun.
    expect(enDate.toLowerCase()).toMatch(/jun/);
    expect(esDate.toLowerCase()).toMatch(/jun/);
  });

  test('formats date range in English and Spanish', () => {
    const start = '2026-08-25';
    const end = '2026-09-24';
    const enRange = formatDateRange(start, end, { dateStyle: 'medium' }, 'en');
    const esRange = formatDateRange(start, end, { dateStyle: 'medium' }, 'es');

    expect(enRange).toContain('2026');
    expect(esRange).toContain('2026');
    expect(enRange.toLowerCase()).toMatch(/aug.*sep/);
    expect(esRange.toLowerCase()).toMatch(/ago.*sep/);
  });

  test('formats numbers with locale-specific conventions', () => {
    const enNum = formatNumber(1250000.5, {}, 'en');
    const esNum = formatNumber(1250000.5, {}, 'es');

    expect(enNum).toBe('1,250,000.5');
    // In Spanish, thousands separator is period or non-breaking space, decimal is comma
    expect(esNum).toMatch(/1[.\s]250[.\s]000,5/);
  });

  test('formats percentage correctly across locales', () => {
    expect(formatPercent(0.155, 1, 'en')).toBe('15.5%');
    expect(formatPercent(0.155, 1, 'es')).toMatch(/15,5\s?%/);
  });

  test('formats currency with language and currency decoupling', () => {
    // USD in English
    const usdInEn = formatCurrency(2500, 'USD', 'en');
    expect(usdInEn).toBe('$2,500.00');

    // USD in Spanish: decoupled, formatted with Spanish decimal conventions and USD code/symbol
    const usdInEs = formatCurrency(2500, 'USD', 'es');
    expect(usdInEs).toMatch(/2500,00|2[.\s]500,00/);
    expect(usdInEs).toMatch(/US\$|\$|USD/);

    // EUR in English: decoupled, formatted with English decimal conventions and EUR symbol
    const eurInEn = formatCurrency(2500, 'EUR', 'en');
    expect(eurInEn).toBe('€2,500.00');

    // EUR in Spanish
    const eurInEs = formatCurrency(2500, 'EUR', 'es');
    expect(eurInEs).toMatch(/(2500,00|2[.\s]500,00)\s?€/);

    // COP in Spanish and English
    const copInEs = formatCurrency(500000, 'COP', 'es');
    expect(copInEs).toMatch(/500[.\s]000/);

    const copInEn = formatCurrency(500000, 'COP', 'en');
    expect(copInEn).toMatch(/500,000/);

    // Zero-decimal currencies (CLP, JPY) respect ISO zero-decimal behavior
    const clpInEn = formatCurrency(15000, 'CLP', 'en');
    expect(clpInEn).toMatch(/15,000/);
    expect(clpInEn).not.toContain('.00');
  });

  test('formats compact currency correctly across locales', () => {
    // USD compact in English
    const usdCompactEn = formatCompactCurrency(1500000, 'USD', 'en');
    expect(usdCompactEn).toMatch(/\$1\.5M|\$1\.50M/);

    // USD compact in Spanish
    const usdCompactEs = formatCompactCurrency(1500000, 'USD', 'es');
    expect(usdCompactEs).toMatch(/1,5\s?M/);

    // COP compact
    const copCompactEs = formatCompactCurrency(25000000, 'COP', 'es');
    expect(copCompactEs).toMatch(/25\s?M/);

    // Empty/null compact currency
    expect(formatCompactCurrency(null)).toBe('—');
    expect(formatCompactCurrency(undefined)).toBe('—');
  });

  test('handles invalid currency codes gracefully without throwing', () => {
    const fallback = formatCurrency(2500, 'NONEXISTENT', 'en');
    expect(fallback).toContain('NONEXISTENT');
    expect(fallback).toContain('2,500');

    const compactFallback = formatCompactCurrency(2500000, 'XYZ', 'en');
    expect(compactFallback).toContain('XYZ');
    expect(compactFallback).toContain('2.5M');
  });

  test('handles invalid or empty inputs gracefully', () => {
    expect(formatDate(null)).toBe('');
    expect(formatDate('invalid-date')).toBe('');
    expect(formatTime(null)).toBe('');
    expect(formatRelativeTime(null)).toBe('');
    expect(formatNumber(null)).toBe('0');
    expect(formatPercent(null)).toBe('0%');
    expect(formatCurrency(null)).toBe('$0.00');
  });
});
