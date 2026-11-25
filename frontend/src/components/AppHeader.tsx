import { ScanText } from 'lucide-react';
import type { ChangeEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { SUPPORTED_LANGUAGES, storeLanguage, type SupportedLanguage } from '../i18n';
import { routeToHash, type AppRoute } from '../routing/routes';

type NavigationSection = 'templates' | 'extract';

const NAVIGATION_ITEMS: { section: NavigationSection; route: AppRoute }[] = [
  { section: 'templates', route: { name: 'templates' } },
  { section: 'extract', route: { name: 'extract' } },
];

const getSection = (route: AppRoute): NavigationSection =>
  route.name === 'extract' ? 'extract' : 'templates';

const isSupportedLanguage = (language: string): language is SupportedLanguage =>
  SUPPORTED_LANGUAGES.some((supported) => supported === language);

export const AppHeader = ({ currentRoute }: { currentRoute: AppRoute }) => {
  const { t, i18n } = useTranslation();
  const currentSection = getSection(currentRoute);

  const changeLanguage = (event: ChangeEvent<HTMLSelectElement>) => {
    const language = event.target.value;
    if (!isSupportedLanguage(language)) {
      return;
    }
    storeLanguage(language);
    void i18n.changeLanguage(language);
  };

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <p className="app-header__brand">
          <ScanText aria-hidden="true" className="icon icon--md" />
          {t('app.title')}
        </p>
        <nav aria-label={t('nav.label')} className="app-nav">
          <ul className="app-nav__list">
            {NAVIGATION_ITEMS.map(({ section, route }) => (
              <li key={section}>
                <a
                  className="app-nav__link"
                  href={routeToHash(route)}
                  aria-current={section === currentSection ? 'page' : undefined}
                >
                  {t(`nav.${section}`)}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="app-header__language">
          <label htmlFor="language-select" className="app-header__language-label">
            {t('language.label')}
          </label>
          <select
            id="language-select"
            className="select select--compact"
            value={i18n.language}
            onChange={changeLanguage}
          >
            {SUPPORTED_LANGUAGES.map((language) => (
              <option key={language} value={language}>
                {t(`language.${language}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
    </header>
  );
};
