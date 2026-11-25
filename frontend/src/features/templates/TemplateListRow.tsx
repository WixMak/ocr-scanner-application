import { Pencil, ScanSearch, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TemplateSummary } from '../../api/schemas';
import { ErrorAlert } from '../../components/ErrorAlert';
import { useDeleteTemplate } from '../../hooks/useTemplateQueries';
import { routeToHash } from '../../routing/routes';
import { formatDateTime } from '../../utils/formatDateTime';

const focusElement = (element: HTMLElement | null) => element?.focus();

export const TemplateListRow = ({ template }: { template: TemplateSummary }) => {
  const { t } = useTranslation('templates');
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const deleteTemplate = useDeleteTemplate();

  return (
    <tr>
      <th scope="row" className="data-table__primary">
        {template.name}
      </th>
      <td className="data-table__numeric">{template.fieldCount}</td>
      <td>{formatDateTime(template.updatedAt)}</td>
      <td>
        {isConfirmingDelete ? (
          <div className="row-actions" role="group" aria-label={t('list.confirmDeleteGroup')}>
            <span className="row-actions__question">
              {t('list.confirmDelete', { name: template.name })}
            </span>
            <button
              type="button"
              className="button button--danger button--small"
              disabled={deleteTemplate.isPending}
              onClick={() => deleteTemplate.mutate(template.id)}
            >
              {deleteTemplate.isPending ? t('list.deleting') : t('list.delete')}
            </button>
            <button
              type="button"
              ref={focusElement}
              className="button button--secondary button--small"
              onClick={() => setIsConfirmingDelete(false)}
            >
              {t('common:actions.cancel')}
            </button>
            {deleteTemplate.isError && <ErrorAlert error={deleteTemplate.error} />}
          </div>
        ) : (
          <div className="row-actions">
            <a
              className="button button--secondary button--small"
              href={routeToHash({ name: 'editTemplate', templateId: template.id })}
              aria-label={t('list.editNamed', { name: template.name })}
            >
              <Pencil aria-hidden="true" className="icon icon--sm" />
              {t('list.edit')}
            </a>
            <a
              className="button button--secondary button--small"
              href={routeToHash({ name: 'extract', templateId: template.id })}
              aria-label={t('list.extractNamed', { name: template.name })}
            >
              <ScanSearch aria-hidden="true" className="icon icon--sm" />
              {t('list.extract')}
            </a>
            <button
              type="button"
              className="button button--ghost-danger button--small"
              aria-label={t('list.deleteNamed', { name: template.name })}
              onClick={() => setIsConfirmingDelete(true)}
            >
              <Trash2 aria-hidden="true" className="icon icon--sm" />
              {t('list.delete')}
            </button>
          </div>
        )}
      </td>
    </tr>
  );
};
