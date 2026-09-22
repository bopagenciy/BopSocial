import React from 'react';
import { render, screen } from '@testing-library/react';
import {
  BrandMark,
  BrandMarkInverted,
  BrandWordmark,
  BrandLogoHorizontal,
  BrandLogoStacked,
  LOGO_ASSET_URL,
} from './BrandLogo';

describe('BrandLogo Component Suite', () => {
  test('BrandMark renders official Bop Social logo image with correct attributes', () => {
    render(<BrandMark size={40} />);
    const img = screen.getByRole('img', { name: /bop social/i });
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('src', LOGO_ASSET_URL);
    expect(img).toHaveAttribute('width', '40');
    expect(img).toHaveAttribute('height', '40');
  });

  test('BrandMarkInverted renders official Bop Social logo image', () => {
    render(<BrandMarkInverted size={32} />);
    const img = screen.getByRole('img', { name: /bop social/i });
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('src', LOGO_ASSET_URL);
  });

  test('BrandWordmark renders Bop and Social wordmark text', () => {
    render(<BrandWordmark height={24} />);
    const wordmark = screen.getByRole('img', { name: /bop social/i });
    expect(wordmark).toBeInTheDocument();
    expect(wordmark).toHaveTextContent('BopSocial');
  });

  test('BrandLogoHorizontal renders both official mark and wordmark', () => {
    const { container } = render(<BrandLogoHorizontal height={36} />);
    const img = container.querySelector('img[alt="Bop Social"]');
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('src', LOGO_ASSET_URL);
    expect(container).toHaveTextContent('BopSocial');
  });

  test('BrandLogoStacked renders stacked mark and wordmark', () => {
    const { container } = render(<BrandLogoStacked height={80} />);
    const img = container.querySelector('img[alt="Bop Social"]');
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('src', LOGO_ASSET_URL);
    expect(container).toHaveTextContent('BopSocial');
  });
});
