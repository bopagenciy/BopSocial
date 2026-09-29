/* ============================================================================
 *  Bop Social — Phase BS-2.7D.1: ROI Visual Localization Residual Closure
 *  Targeted Verification Test Suite
 * ============================================================================ */
import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n from '../../i18n/config';
import ROICalculatorPage from '../ROICalculatorPage';
import { formatMonthName, formatCurrency } from '../../utils/formatters';
import * as useDataModule from '../../hooks/useData';
import { roiAPI } from '../../services/api';

// ── Polyfills ──────────────────────────────────────────────────────────────────
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// ── Mocks ──────────────────────────────────────────────────────────────────────
jest.mock('../../hooks/useData', () => ({
  __esModule: true,
  useClients: jest.fn(),
}));

jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {},
  roiAPI: {
    getSettings: jest.fn(),
    getLive: jest.fn(),
    getReports: jest.fn(),
    saveSettings: jest.fn(() => Promise.resolve({ data: {} })),
    saveReport: jest.fn(() => Promise.resolve({ data: {} })),
  },
  clientsAPI: {
    list: jest.fn(() => Promise.resolve({ data: [{ id: 1, company: 'Acme Corp', currency: 'USD' }] })),
    get: jest.fn(() => Promise.resolve({ data: { id: 1, company: 'Acme Corp', currency: 'USD' } })),
  },
}));

describe('Phase BS-2.7D.1: ROI Visual Localization Residual Closure', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    useDataModule.useClients.mockReturnValue({
      clients: [{ id: 1, company: 'Acme Corp', currency: 'USD' }],
      loading: false,
    });

    roiAPI.getReports.mockResolvedValue({ data: [] });
    roiAPI.getSettings.mockResolvedValue({
      data: {
        facebook_budget: 400,
        instagram_budget: 200,
        youtube_budget: 0,
        linkedin_budget: 0,
        gmb_budget: 0,
        agency_fee: 150,
        avg_sale_value: 120,
        conversion_rate: 2.0,
        lead_to_sale_rate: 15,
        monthly_revenue_goal: 3000,
        monthly_leads_goal: 30,
        currency: 'USD',
      },
    });

    roiAPI.getLive.mockResolvedValue({
      data: {
        total_investment: 750,
        estimated_revenue: 0,
        roi_percentage: -100,
        per_dollar_earned: 0.0,
        cost_per_click: 1.2,
        cost_per_lead: 45.0,
        cost_per_sale: 0,
        total_clicks: 625,
        total_website_clicks: 500,
        estimated_leads: 10,
        estimated_sales: 0,
        has_data: true,
      },
    });

    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  afterEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  // 1. ROI page English heading
  it('1. displays ROI Calculator heading in English', async () => {
    render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: 'ROI Calculator' })).toBeInTheDocument();
    });
  });

  // 2. ROI page Spanish heading
  it('2. displays Calculadora de ROI heading in Spanish', async () => {
    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: 'Calculadora de ROI' })).toBeInTheDocument();
    });
  });

  // 3. ROI subtitle EN/ES
  it('3. displays localized subtitle in English and Spanish', async () => {
    const { unmount } = render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Measure the return on your social media investment')).toBeInTheDocument();
    });
    unmount();

    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Mide el retorno de tu inversión en redes sociales')).toBeInTheDocument();
    });
  });

  // 4. Monthly Investment label EN/ES
  it('4. displays Monthly Investment in English and Inversión mensual in Spanish', async () => {
    const { unmount } = render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: /Monthly Investment/i })).toBeInTheDocument();
    });
    unmount();

    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: /Inversión mensual/i })).toBeInTheDocument();
    });
  });

  // 5. Currency label EN/ES
  it('5. displays Currency: label in English and Moneda: in Spanish', async () => {
    const { unmount } = render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Currency:')).toBeInTheDocument();
    });
    unmount();

    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Moneda:')).toBeInTheDocument();
    });
  });

  // 6. Settings saved message EN/ES
  it('6. displays Settings saved banner and description in English and Spanish', async () => {
    const { unmount } = render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Settings saved')).toBeInTheDocument();
      expect(screen.getByText('Click Edit Settings to change budgets and business numbers.')).toBeInTheDocument();
    });
    unmount();

    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Configuración guardada')).toBeInTheDocument();
      expect(screen.getByText('Haz clic en Editar configuración para cambiar presupuestos y datos del negocio.')).toBeInTheDocument();
    });
  });

  // 7. ROI status label EN/ES
  it('7. displays Losing Money in English and Generando pérdidas in Spanish', async () => {
    const { unmount } = render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Losing Money')).toBeInTheDocument();
    });
    unmount();

    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Generando pérdidas')).toBeInTheDocument();
    });
  });

  // 8. Dynamic ROI sentence EN/ES
  it('8. dynamically formats and interpolates ROI sentence in English and Spanish', async () => {
    const { unmount } = render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/For every \$1\.00 spent you earn \$0\.00 back/i)).toBeInTheDocument();
    });
    unmount();

    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Por cada 1,00\s?US\$ invertido, recuperas 0,00\s?US\$/i)).toBeInTheDocument();
    });
  });

  // 9. Month September -> septiembre in Spanish
  it('9. formats month number 9 as septiembre in Spanish using formatMonthName', () => {
    expect(formatMonthName(9, 'es')).toBe('septiembre');
  });

  // 10. Month remains September in English
  it('10. formats month number 9 as September in English using formatMonthName', () => {
    expect(formatMonthName(9, 'en')).toBe('September');
  });

  // 11. Currency remains USD while toggling ES/EN
  it('11. preserves currency code USD when toggling between English and Spanish', async () => {
    render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Currency|Moneda/i)).toHaveValue('USD');
    });

    // Toggle to Spanish
    await act(async () => {
      await i18n.changeLanguage('es');
    });

    expect(screen.getByLabelText(/Currency|Moneda/i)).toHaveValue('USD');

    // Toggle back to English
    await act(async () => {
      await i18n.changeLanguage('en');
    });

    expect(screen.getByLabelText(/Currency|Moneda/i)).toHaveValue('USD');
  });

  // 12. No hardcoded English residuals in the tested ROI surface in Spanish
  it('12. renders localized cards without English residuals in Spanish mode', async () => {
    await act(async () => {
      await i18n.changeLanguage('es');
    });

    render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Retorno de la inversión')).toBeInTheDocument();
      expect(screen.getByText(/Total invertido/i)).toBeInTheDocument();
      expect(screen.getByText(/Ingresos estimados/i)).toBeInTheDocument();
      expect(screen.getByText('Embudo de conversión')).toBeInTheDocument();
      expect(screen.getByText('Eficiencia de costos')).toBeInTheDocument();
      expect(screen.getByText('Editar configuración')).toBeInTheDocument();
      expect(screen.getByText('Guardar informe')).toBeInTheDocument();
    });
  });

  // 13. No hardcoded currency symbol regression
  it('13. renders monetary amounts with dynamic formatCurrency and zero hardcoded Rupee symbols', async () => {
    await act(async () => {
      await i18n.changeLanguage('es');
    });

    const { container } = render(
      <MemoryRouter>
        <ROICalculatorPage clientId={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Retorno de la inversión')).toBeInTheDocument();
    });

    expect(container.textContent).not.toContain('₹');
  });
});
