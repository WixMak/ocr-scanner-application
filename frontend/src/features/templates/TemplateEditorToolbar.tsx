import { Plus, Save, ScanSearch } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { routeToHash } from '../../routing/routes';
import { TEMPLATE_NAME_MAX_LENGTH } from './templateValidation';

export const TEMPLATE_NAME_INPUT_ID = 'template-name';
const NAME_ERROR_ID = `${TEMPLATE_NAME_INPUT_ID}-error`;

type TemplateEditorToolbarProps = {
  name: string;
  isNameInvalid: boolean;
  isSaving: boolean;
  savedTemplateId: string | null;
  onNameChange: (name: string) => void;
  onAddField: () => void;
};

export const TemplateEditorToolbar = ({
  name,
  isNameInvalid,
  isSaving,
  savedTemplateId,
  onNameChange,
  onAddField,
}: TemplateEditorToolbarProps) => {
  const { t } = useTranslation('templates');

  return (
    <div className="editor__toolbar">
      <div className="form-control editor__name">
        <label htmlFor={TEMPLATE_NAME_INPUT_ID}>{t('editor.name')}</label>
        <input
          id={TEMPLATE_NAME_INPUT_ID}
          className="input"
          value={name}
          maxLength={TEMPLATE_NAME_MAX_LENGTH}
          required
          aria-invalid={isNameInvalid ? true : undefined}
          aria-describedby={isNameInvalid ? NAME_ERROR_ID : undefined}
          onChange={(event) => onNameChange(event.target.value)}
        />
        {isNameInvalid && (
          <p id={NAME_ERROR_ID} className="field-error">
            {t('validation.nameRequired')}
          </p>
        )}
      </div>
      <div className="editor__actions">
        <button type="button" className="button button--secondary" onClick={onAddField}>
          <Plus aria-hidden="true" className="icon icon--sm" />
          {t('editor.addField')}
        </button>
        <button type="submit" className="button button--primary" disabled={isSaving}>
          <Save aria-hidden="true" className="icon icon--sm" />
          {isSaving ? t('editor.saving') : t('editor.save')}
        </button>
        {savedTemplateId && (
          <a
            className="button button--secondary"
            href={routeToHash({ name: 'extract', templateId: savedTemplateId })}
          >
            <ScanSearch aria-hidden="true" className="icon icon--sm" />
            {t('editor.useForExtraction')}
          </a>
        )}
      </div>
    </div>
  );
};
