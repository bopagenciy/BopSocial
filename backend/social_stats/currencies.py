# ============================================================================
#  Social Stats — Social Media Management & Marketing Platform
#  Canonical Currencies Authority (ISO 4217)
# ============================================================================
"""
Central definition of canonical currency choices supported across Bop Social
workspaces, ad integrations (CTWA / Meta Ads), and financial formatting.
"""

CURRENCY_CHOICES = [
    ('USD', 'USD - US Dollar'),
    ('COP', 'COP - Colombian Peso'),
    ('EUR', 'EUR - Euro'),
    ('GBP', 'GBP - British Pound'),
    ('MXN', 'MXN - Mexican Peso'),
    ('CAD', 'CAD - Canadian Dollar'),
    ('INR', 'INR - Indian Rupee'),
    ('BRL', 'BRL - Brazilian Real'),
    ('ARS', 'ARS - Argentine Peso'),
    ('CLP', 'CLP - Chilean Peso'),
    ('PEN', 'PEN - Peruvian Sol'),
]

SUPPORTED_CURRENCIES = [code for code, _ in CURRENCY_CHOICES]
DEFAULT_CURRENCY = 'USD'
