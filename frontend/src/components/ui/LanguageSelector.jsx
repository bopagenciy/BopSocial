/* ============================================================================
 *  Bop Social — Language Selector Component
 *  Accessible, keyboard-friendly language picker supporting English and Spanish.
 *  Adheres to Bop Social design system tokens.
 * ========================================================================== */
import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe, Check, ChevronDown } from 'lucide-react';
import { SUPPORTED_LANGUAGES, changePlatformLanguage } from '../../i18n/config';

export default function LanguageSelector({
  size = 'md',
  variant = 'ghost',
  darkHero = false,
  showLabel = true,
  onLanguageChange,
  className = '',
  style = {},
}) {
  const { i18n, t } = useTranslation('common');
  const [isOpen, setIsOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const containerRef = useRef(null);
  const buttonRef = useRef(null);

  const currentCode = (i18n.language || 'en').substring(0, 2).toLowerCase();
  const currentLang = SUPPORTED_LANGUAGES.find((l) => l.code === currentCode) || SUPPORTED_LANGUAGES[0];

  // Close when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleSelect = async (code) => {
    await changePlatformLanguage(code);
    setIsOpen(false);
    if (onLanguageChange) {
      onLanguageChange(code);
    }
    if (buttonRef.current) {
      buttonRef.current.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      setIsOpen(false);
      if (buttonRef.current) buttonRef.current.focus();
      return;
    }

    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        setIsOpen(true);
        setFocusedIndex(0);
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setFocusedIndex((prev) => (prev + 1) % SUPPORTED_LANGUAGES.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setFocusedIndex((prev) => (prev - 1 + SUPPORTED_LANGUAGES.length) % SUPPORTED_LANGUAGES.length);
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (focusedIndex >= 0 && focusedIndex < SUPPORTED_LANGUAGES.length) {
        handleSelect(SUPPORTED_LANGUAGES[focusedIndex].code);
      }
    } else if (e.key === 'Tab') {
      setIsOpen(false);
    }
  };

  const isSmall = size === 'sm';
  const buttonPadding = isSmall ? '6px 10px' : '8px 14px';
  const fontSize = isSmall ? 13 : 14;

  const textColor = darkHero
    ? '#FFFFFF'
    : 'var(--text-primary)';
  const iconColor = darkHero
    ? 'rgba(255, 255, 255, 0.8)'
    : 'var(--text-secondary)';
  const hoverBg = darkHero
    ? 'rgba(255, 255, 255, 0.12)'
    : 'var(--surface-hover)';

  return (
    <div
      ref={containerRef}
      className={`bop-language-selector ${className}`}
      style={{ position: 'relative', display: 'inline-block', ...style }}
      onKeyDown={handleKeyDown}
    >
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label={t('languages.select_language', 'Select language')}
        onClick={() => {
          setIsOpen(!isOpen);
          setFocusedIndex(-1);
        }}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: buttonPadding,
          fontSize,
          fontWeight: 500,
          color: textColor,
          background: isOpen ? hoverBg : 'transparent',
          border: '1px solid',
          borderColor: darkHero ? 'rgba(255, 255, 255, 0.2)' : 'var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          cursor: 'pointer',
          fontFamily: 'inherit',
          transition: 'var(--transition-fast)',
          outline: 'none',
        }}
        onMouseOver={(e) => {
          e.currentTarget.style.background = hoverBg;
        }}
        onMouseOut={(e) => {
          if (!isOpen) e.currentTarget.style.background = 'transparent';
        }}
      >
        <Globe size={isSmall ? 14 : 16} style={{ color: iconColor }} />
        {showLabel ? (
          <span>{currentLang.shortLabel}</span>
        ) : (
          <span className="sr-only">{currentLang.label}</span>
        )}
        <ChevronDown
          size={isSmall ? 12 : 14}
          style={{
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0)',
            transition: 'transform 160ms var(--ease-out)',
            color: iconColor,
          }}
        />
      </button>

      {isOpen && (
        <ul
          role="listbox"
          aria-label={t('languages.select_language', 'Select language')}
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            right: 0,
            zIndex: 1100,
            minWidth: 150,
            padding: '4px',
            margin: 0,
            listStyle: 'none',
            background: 'var(--surface-card)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-lg)',
            animation: 'lang-popover-in 140ms var(--ease-out)',
          }}
        >
          {SUPPORTED_LANGUAGES.map((lang, idx) => {
            const isSelected = lang.code === currentCode;
            const isFocused = idx === focusedIndex;

            return (
              <li
                key={lang.code}
                role="option"
                aria-selected={isSelected}
                tabIndex={-1}
                onClick={() => handleSelect(lang.code)}
                onMouseEnter={() => setFocusedIndex(idx)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 12px',
                  fontSize: 13,
                  fontWeight: isSelected ? 600 : 400,
                  color: isSelected ? 'var(--brand-primary-hover)' : 'var(--text-primary)',
                  background: isFocused || isSelected ? 'var(--surface-hover)' : 'transparent',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  transition: 'var(--transition-fast)',
                }}
              >
                <span>{lang.label}</span>
                {isSelected && <Check size={14} style={{ color: 'var(--brand-primary-hover)' }} />}
              </li>
            );
          })}
        </ul>
      )}

      <style>{`
        @keyframes lang-popover-in {
          from { opacity: 0; transform: translateY(-4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
