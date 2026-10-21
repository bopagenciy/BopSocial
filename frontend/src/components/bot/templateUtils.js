/* ============================================================================
 *  Bop Social — Bot Flow Template Localization Utilities
 * ========================================================================== */

/**
 * Resolves user-facing display label for a bot template without altering
 * canonical IDs, database names, or API payloads.
 *
 * @param {string} name - Canonical template name from database/API
 * @param {Function} t - i18next translation function (messaging namespace)
 * @returns {string} Localized display name or original canonical name as fallback
 */
export function getTemplateDisplayName(name, t) {
  if (!name || typeof t !== 'function') return name || '';
  const slug = String(name)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
  const key = `bot_templates.built_in.${slug}.name`;
  const val = t(key, { defaultValue: '' });
  return val || name;
}

/**
 * Resolves user-facing display description for a bot template without altering
 * canonical IDs or database values.
 *
 * @param {string} name - Canonical template name
 * @param {string} fallbackDesc - Original description from template object
 * @param {Function} t - i18next translation function (messaging namespace)
 * @returns {string} Localized description or original fallback description
 */
export function getTemplateDisplayDescription(name, fallbackDesc, t) {
  if (!name || typeof t !== 'function') return fallbackDesc || '';
  const slug = String(name)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
  const key = `bot_templates.built_in.${slug}.description`;
  const val = t(key, { defaultValue: '' });
  return val || fallbackDesc || '';
}
