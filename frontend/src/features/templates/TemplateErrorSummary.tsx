import { useTranslation } from 'react-i18next';
import type { TemplateField } from '../../api/schemas';
import { fieldKeyInputId } from './FieldEditorRow';
import type { TemplateValidation } from './templateValidation';

const focusOnMount = (summary: HTMLDivElement | null) => summary?.focus();

type TemplateErrorSummaryProps = {
  validation: TemplateValidation;
  fields: TemplateField[];
  nameInputId: string;
};

export const TemplateErrorSummary = ({
  validation,
  fields,
  nameInputId,
}: TemplateErrorSummaryProps) => {
  const { t } = useTranslation('templates');
  const fieldProblems = fields.flatMap((field) => {
    const problem = validation.keyProblems.get(field.id);
    return problem ? [{ field, problem }] : [];
  });

  return (
    <div
      ref={focusOnMount}
      tabIndex={-1}
      role="alert"
      aria-labelledby="error-summary-heading"
      className="error-summary"
    >
      <h2 id="error-summary-heading" className="error-summary__title">
        {t('validation.summaryHeading')}
      </h2>
      <ul className="error-summary__list">
        {validation.isNameMissing && (
          <li>
            <a href={`#${nameInputId}`}>{t('validation.nameRequired')}</a>
          </li>
        )}
        {fieldProblems.map(({ field, problem }) => (
          <li key={field.id}>
            <a href={`#${fieldKeyInputId(field.id)}`}>
              {t(`validation.summaryKey.${problem}`, {
                name: field.label || field.key || t('validation.unnamedField'),
              })}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
};
