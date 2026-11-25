import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
import enCommon from '../locales/en/common.json';
import enExtraction from '../locales/en/extraction.json';
import enTemplates from '../locales/en/templates.json';
import zhCommon from '../locales/zh-CN/common.json';
import zhExtraction from '../locales/zh-CN/extraction.json';
import zhTemplates from '../locales/zh-CN/templates.json';

export const SUPPORTED_LANGUAGES = ['en', 'zh-CN'] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const DEFAULT_LANGUAGE: SupportedLanguage = 'en';
export const NAMESPACES = ['common', 'templates', 'extraction'] as const;
const LANGUAGE_STORAGE_KEY = 'ocr-form-scanner.language';
const CHINESE_LANGUAGE_PREFIX = 'zh';

export const resources = {
  en: { common: enCommon, templates: enTemplates, extraction: enExtraction },
  'zh-CN': { common: zhCommon, templates: zhTemplates, extraction: zhExtraction },
} as const;

const isSupportedLanguage = (language: string | null): language is SupportedLanguage =>
  SUPPORTED_LANGUAGES.some((supported) => supported === language);

const readStoredLanguage = (): string | null => {
  try {
    return window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
  } catch {
    return null;
  }
};

export const storeLanguage = (language: SupportedLanguage): void => {
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Storage can be blocked (private mode); the choice then lasts for this visit only.
  }
};

export const detectInitialLanguage = (): SupportedLanguage => {
  const storedLanguage = readStoredLanguage();
  if (isSupportedLanguage(storedLanguage)) {
    return storedLanguage;
  }
  return navigator.language.startsWith(CHINESE_LANGUAGE_PREFIX) ? 'zh-CN' : DEFAULT_LANGUAGE;
};

export const initI18n = (language: SupportedLanguage = detectInitialLanguage()) => {
  i18next.on('languageChanged', (changedLanguage) => {
    document.documentElement.lang = changedLanguage;
  });
  return i18next.use(initReactI18next).init({
    resources,
    lng: language,
    fallbackLng: DEFAULT_LANGUAGE,
    ns: NAMESPACES,
    defaultNS: 'common',
    interpolation: { escapeValue: false },
    returnNull: false,
  });
};
