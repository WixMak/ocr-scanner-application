import { useTranslation } from 'react-i18next';
import { AppHeader } from './components/AppHeader';
import { HealthBanner } from './components/HealthBanner';
import { ExtractPage } from './features/extraction/ExtractPage';
import { TemplateEditorPage } from './features/templates/TemplateEditorPage';
import { TemplateListPage } from './features/templates/TemplateListPage';
import { routeToHash, type AppRoute } from './routing/routes';
import { useHashRoute } from './routing/useHashRoute';

const MAIN_CONTENT_ID = 'main-content';

const RoutePage = ({ route }: { route: AppRoute }) => {
  switch (route.name) {
    case 'templates':
      return <TemplateListPage />;
    case 'newTemplate':
      return <TemplateEditorPage />;
    case 'editTemplate':
      return <TemplateEditorPage templateId={route.templateId} />;
    case 'extract':
      return <ExtractPage initialTemplateId={route.templateId} />;
  }
};

export const App = () => {
  const { t } = useTranslation();
  const route = useHashRoute();

  return (
    <>
      <a className="skip-link" href={`#${MAIN_CONTENT_ID}`}>
        {t('app.skipToContent')}
      </a>
      <AppHeader currentRoute={route} />
      <main id={MAIN_CONTENT_ID} className="app-main">
        <HealthBanner />
        <RoutePage key={routeToHash(route)} route={route} />
      </main>
    </>
  );
};
