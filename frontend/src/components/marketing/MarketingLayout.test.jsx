import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MarketingLayout from './MarketingLayout';

describe('MarketingLayout Navigation & MegaMenu Suite', () => {
  beforeEach(() => {
    // Reset window dimensions to desktop
    window.innerWidth = 1200;
  });

  test('renders logo and top navigation items', () => {
    render(
      <MemoryRouter>
        <MarketingLayout><div>Test Content</div></MarketingLayout>
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: /bop social home/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /product/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /solutions/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /resources/i })).toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  test('opens Product mega menu with opaque surface on hover/click and displays items', () => {
    render(
      <MemoryRouter>
        <MarketingLayout><div>Test Content</div></MarketingLayout>
      </MemoryRouter>
    );

    const productBtn = screen.getByRole('button', { name: /product/i });
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();

    // Click to open
    fireEvent.click(productBtn);

    const menu = screen.getByRole('menu');
    expect(menu).toBeInTheDocument();
    expect(menu).toHaveStyle({ background: 'var(--surface-card)' });
    expect(within(menu).getByText('Analytics')).toBeInTheDocument();
    expect(within(menu).getByText('Composer')).toBeInTheDocument();
    expect(within(menu).getByText('Cross-platform metrics')).toBeInTheDocument();
  });

  test('closes mega menu when Escape key is pressed', () => {
    render(
      <MemoryRouter>
        <MarketingLayout><div>Test Content</div></MarketingLayout>
      </MemoryRouter>
    );

    const productBtn = screen.getByRole('button', { name: /product/i });
    fireEvent.click(productBtn);
    expect(screen.getByRole('menu')).toBeInTheDocument();

    // Press Escape
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  test('closes mega menu when clicked outside the header', () => {
    render(
      <MemoryRouter>
        <MarketingLayout>
          <div data-testid="outside-canvas">Outside Canvas</div>
        </MarketingLayout>
      </MemoryRouter>
    );

    const solutionsBtn = screen.getByRole('button', { name: /solutions/i });
    fireEvent.click(solutionsBtn);
    expect(screen.getByRole('menu')).toBeInTheDocument();

    // Click outside
    fireEvent.pointerDown(screen.getByTestId('outside-canvas'));
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  test('toggles mega menu on successive trigger clicks', () => {
    render(
      <MemoryRouter>
        <MarketingLayout><div>Content</div></MarketingLayout>
      </MemoryRouter>
    );

    const resourcesBtn = screen.getByRole('button', { name: /resources/i });
    // First click opens
    fireEvent.click(resourcesBtn);
    const menu = screen.getByRole('menu');
    expect(menu).toBeInTheDocument();
    expect(within(menu).getByText('Help Center')).toBeInTheDocument();

    // Second click closes
    fireEvent.click(resourcesBtn);
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  test('renders active NavLink with high-contrast active background pill and font-weight', () => {
    render(
      <MemoryRouter initialEntries={['/customers']}>
        <MarketingLayout><div>Content</div></MarketingLayout>
      </MemoryRouter>
    );

    const nav = screen.getByRole('navigation');
    const customersLink = within(nav).getByRole('link', { name: /^customers$/i });
    expect(customersLink).toBeInTheDocument();
    expect(customersLink).toHaveStyle({
      background: 'var(--surface-hover)',
      fontWeight: 600,
    });
  });

  test('renders Built for the Bop Universe in marketing footer', () => {
    render(
      <MemoryRouter>
        <MarketingLayout><div>Content</div></MarketingLayout>
      </MemoryRouter>
    );

    expect(screen.getByText(/Built for the Bop Universe/i)).toBeInTheDocument();
  });
});
