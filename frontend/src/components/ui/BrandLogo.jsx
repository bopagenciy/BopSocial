/* ============================================================================
 *  Social Stats — Social Media Management & Marketing Platform
 *  Author    : Chandrabhan Shekhawat
 *  Company   : Gigai Kripa Services
 *  Website   : https://gigaikripaservices.com/
 *  Copyright (c) 2026 Chandrabhan Shekhawat / Gigai Kripa Services.
 *  Released under the MIT License — see LICENSE. Keep this notice.
 * ========================================================================== */
/**
 * Bop Social logo — official corporate brand asset and wordmark.
 *
 * Five variants kept compatible with the prior API so consumers don't
 * have to change:
 *   BrandMark            — square official brand mark (icon-only)
 *   BrandMarkInverted    — same official brand mark for dark surfaces
 *   BrandWordmark        — corporate wordmark (text only)
 *   BrandLogoHorizontal  — official mark + wordmark, side by side
 *   BrandLogoStacked     — official mark + wordmark, stacked
 */

export const LOGO_ASSET_URL = process.env.PUBLIC_URL ? `${process.env.PUBLIC_URL}/LogoBopSocial.png` : '/LogoBopSocial.png';

function OfficialLogoImg({ size = 40, className, style: extraStyle, inverted = false }) {
  return (
    <img
      src={LOGO_ASSET_URL}
      alt="Bop Social"
      width={size}
      height={size}
      className={className}
      style={{
        display: 'block',
        width: size,
        height: size,
        objectFit: 'contain',
        borderRadius: Math.max(4, Math.round(size * 0.2)),
        flexShrink: 0,
        ...extraStyle,
      }}
    />
  );
}

function WordmarkText({ height = 22, color = 'currentColor' }) {
  const fontSize = Math.round(height * 0.86);
  return (
    <span
      role="img"
      aria-label="Bop Social"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        fontFamily: 'var(--font-display, var(--font-sans, Inter), system-ui, sans-serif)',
        fontWeight: 800,
        fontSize,
        letterSpacing: '-0.03em',
        lineHeight: 1,
        color,
        whiteSpace: 'nowrap',
        userSelect: 'none',
      }}
    >
      <span style={{ color: 'var(--text-primary, #1E202A)' }}>Bop</span>
      <span style={{ color: 'var(--brand-primary, #F5A623)', marginLeft: '0.22em' }}>Social</span>
    </span>
  );
}

export function BrandMark({ size = 40, className, style: extraStyle }) {
  return (
    <span className={className} style={{ display: 'inline-flex', ...extraStyle }}>
      <OfficialLogoImg size={size} />
    </span>
  );
}

export function BrandMarkInverted({ size = 40, className, style: extraStyle }) {
  return (
    <span className={className} style={{ display: 'inline-flex', ...extraStyle }}>
      <OfficialLogoImg size={size} inverted />
    </span>
  );
}

export function BrandWordmark({ height = 22, className, style: extraStyle }) {
  return (
    <span className={className} style={{ display: 'inline-flex', height, ...extraStyle }}>
      <WordmarkText height={height} />
    </span>
  );
}

export function BrandLogoHorizontal({ height = 36, className, style: extraStyle }) {
  const markSize = Math.round(height);
  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: Math.round(height * 0.32),
        height,
        ...extraStyle,
      }}
    >
      <OfficialLogoImg size={markSize} />
      <WordmarkText height={Math.round(height * 0.65)} />
    </span>
  );
}

export function BrandLogoStacked({ height = 100, className, style: extraStyle }) {
  const markSize = Math.round(height * 0.6);
  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: Math.round(height * 0.12),
        height,
        ...extraStyle,
      }}
    >
      <OfficialLogoImg size={markSize} />
      <WordmarkText height={Math.round(height * 0.24)} />
    </span>
  );
}
