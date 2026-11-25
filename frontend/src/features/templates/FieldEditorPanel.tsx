import { useRef } from 'react';
import { useTranslation } from 'react-i18next';
import type { PageSize, TemplateField } from '../../api/schemas';
import { groupByPage, pageAt } from '../../utils/pages';
import { toImageSize } from './boxGeometry';
import { FieldEditorRow } from './FieldEditorRow';
import type { FieldKeyProblem } from './templateValidation';
import type { FieldEditorActions } from './useFieldEditor';

type FieldEditorPanelProps = {
  fields: TemplateField[];
  keyProblems: ReadonlyMap<string, FieldKeyProblem>;
  selectedFieldId: string | null;
  addedFieldId: string | null;
  pages: PageSize[];
  actions: FieldEditorActions;
};

export const FieldEditorPanel = ({
  fields,
  keyProblems,
  selectedFieldId,
  addedFieldId,
  pages,
  actions,
}: FieldEditorPanelProps) => {
  const { t } = useTranslation('templates');
  const headingRef = useRef<HTMLHeadingElement>(null);
  const isMultiPage = pages.length > 1;

  const rowActions: FieldEditorActions = {
    ...actions,
    remove: (fieldId) => {
      actions.remove(fieldId);
      headingRef.current?.focus();
    },
  };

  const renderRows = (rowFields: TemplateField[]) => (
    <ul className="field-list">
      {rowFields.map((field) => (
        <FieldEditorRow
          key={field.id}
          field={field}
          keyProblem={keyProblems.get(field.id)}
          isSelected={field.id === selectedFieldId}
          shouldFocusKey={field.id === addedFieldId}
          imageSize={toImageSize(pageAt(pages, field.pageIndex))}
          actions={rowActions}
        />
      ))}
    </ul>
  );

  const renderPageGroups = () =>
    groupByPage(fields, pages.length).map((group) => (
      <section
        key={group.pageIndex}
        className="field-group"
        aria-labelledby={`field-group-${group.pageIndex}`}
      >
        <h3 id={`field-group-${group.pageIndex}`} className="field-group__heading">
          {t('common:pages.page', { number: group.pageIndex + 1 })}
        </h3>
        {renderRows(group.items)}
      </section>
    ));

  const renderFields = () => {
    if (fields.length === 0) {
      return <p className="empty-state">{t('editor.noFields')}</p>;
    }
    return isMultiPage ? renderPageGroups() : renderRows(fields);
  };

  return (
    <section className="panel editor__fields" aria-labelledby="editor-fields-heading">
      <h2 id="editor-fields-heading" ref={headingRef} tabIndex={-1} className="panel__title">
        {t('editor.fieldsHeading', { count: fields.length })}
      </h2>
      {renderFields()}
    </section>
  );
};
