import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import LanguageSelector from './LanguageSelector';
import i18n, { LANGUAGE_STORAGE_KEY } from '../../i18n/config';

describe('LanguageSelector Component Suite', () => {
  beforeEach(async () => {
    localStorage.clear();
    await i18n.changeLanguage('en');
  });

  test('renders button with current language label and globe icon', () => {
    render(<LanguageSelector />);

    const button = screen.getByRole('button', { name: /select language/i });
    expect(button).toBeInTheDocument();
    expect(button).toHaveTextContent('EN');
    expect(button).toHaveAttribute('aria-haspopup', 'listbox');
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });

  test('opens dropdown on click, shows options, and changes language to Spanish', async () => {
    const onLanguageChange = jest.fn();
    render(<LanguageSelector onLanguageChange={onLanguageChange} />);

    const button = screen.getByRole('button', { name: /select language/i });
    fireEvent.click(button);

    expect(button).toHaveAttribute('aria-expanded', 'true');
    const listbox = screen.getByRole('listbox');
    expect(listbox).toBeInTheDocument();

    const spanishOption = screen.getByRole('option', { name: /español/i });
    expect(spanishOption).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(spanishOption);
    });

    expect(i18n.language).toBe('es');
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('es');
    expect(onLanguageChange).toHaveBeenCalledWith('es');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  test('keyboard navigation closes menu on Escape', () => {
    render(<LanguageSelector />);

    const button = screen.getByRole('button', { name: /select language/i });
    fireEvent.click(button);
    expect(screen.getByRole('listbox')).toBeInTheDocument();

    fireEvent.keyDown(button, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });
});
