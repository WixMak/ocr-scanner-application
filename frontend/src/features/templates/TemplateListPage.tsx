import { FilePlus2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { ErrorAlert } from '../../components/ErrorAlert';
import { PageHeading } from '../../components/PageHeading';
import { useTemplateList } from '../../hooks/useTemplateQueries';
import { routeToHash } from '../../routing/routes';
import { TemplateListRow } from './TemplateListRow';

const NEW_TEMPLATE_HREF = routeToHash({ name: 'newTemplate' });

export const TemplateListPage = () => {
  const { t } = useTranslation('templates');
  const templates = useTemplateList();

  return (
    <>
      <div className="page-header">
        <div>
          <PageHeading>{t('list.heading')}</PageHeading>
          <p className="page-intro">{t('list.intro')}</p>
        </div>
        <a className="button button--primary" href={NEW_TEMPLATE_HREF}>
          <FilePlus2 aria-hidden="true" className="icon icon--sm" />
          {t('list.newTemplate')}
        </a>
      </div>

      {templates.isPending && (
        <p role="status" className="loading-text">
          {t('list.loading')}
        </p>
      )}
      {templates.isError && <ErrorAlert error={templates.error} />}
      {templates.data?.length === 0 && (
        <div className="panel empty-panel">
          <p className="empty-state">{t('list.empty')}</p>
          <a className="button button--primary" href={NEW_TEMPLATE_HREF}>
            {t('list.createFirst')}
          </a>
        </div>
      )}
      {templates.data && templates.data.length > 0 && (
        <div className="panel table-scroller">
          <table className="data-table">
            <caption className="visually-hidden">{t('list.caption')}</caption>
            <thead>
              <tr>
                <th scope="col">{t('list.columns.name')}</th>
                <th scope="col" className="data-table__numeric">
                  {t('list.columns.fields')}
                </th>
                <th scope="col">{t('list.columns.updated')}</th>
                <th scope="col">{t('list.columns.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {templates.data.map((template) => (
                <TemplateListRow key={template.id} template={template} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
};
