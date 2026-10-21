import React from 'react';
import { render } from '@testing-library/react';
import Meta from './Meta';

describe('Meta Component Brand & Title Suite', () => {
  afterEach(() => {
    document.title = '';
  });

  test('sets document title with Bop Social suffix by default', () => {
    render(<Meta title="Customers" />);
    expect(document.title).toBe('Customers · Bop Social');
  });

  test('sets exact title when noSuffix is true', () => {
    render(<Meta title="Bop Social — Unified Platform" noSuffix />);
    expect(document.title).toBe('Bop Social — Unified Platform');
  });

  test('defaults to full brand title when title is empty', () => {
    render(<Meta />);
    expect(document.title).toBe('Bop Social — The Marketing OS for Modern Teams');
  });
});
