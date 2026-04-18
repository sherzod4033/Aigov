import { normalizeLocale } from '../i18n';

const INTL_LOCALES = {
    ru: 'ru-RU',
    tg: 'tg-TJ',
};

export const getIntlLocale = (locale) => INTL_LOCALES[normalizeLocale(locale) || 'tg'];

export const formatLocaleDate = (value, locale, options, fallback = '-') => {
    if (!value) return fallback;

    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return fallback;

    return new Intl.DateTimeFormat(getIntlLocale(locale), options).format(date);
};

export const formatDocumentLanguage = (language) => {
    const normalized = normalizeLocale(language);

    if (normalized === 'tg') {
        return { code: 'tg', text: 'TG', className: 'bg-yellow-100 text-yellow-800' };
    }

    if (normalized === 'ru') {
        return { code: 'ru', text: 'RU', className: 'bg-blue-100 text-blue-700' };
    }

    return { code: null, text: String(language || '—').trim().toUpperCase() || '—', className: 'bg-slate-100 text-slate-700' };
};
