import {
  formatDate,
  formatTime,
  formatRelativeTime,
  formatNumber,
  formatPercent,
  formatCurrency,
  getResolvedLocale,
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
