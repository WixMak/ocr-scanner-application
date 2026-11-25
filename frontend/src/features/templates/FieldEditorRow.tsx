import { Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { FIELD_TYPES, fieldTypeSchema, type TemplateField } from '../../api/schemas';
import { BOX_DIMENSIONS, setBoxDimension, type ImageSize } from './boxGeometry';
import { ChoiceOptionsEditor } from './ChoiceOptionsEditor';
import {
  FIELD_KEY_MAX_LENGTH,
  FIELD_LABEL_MAX_LENGTH,
  type FieldKeyProblem,
} from './templateValidation';
import type { FieldEditorActions } from './useFieldEditor';
import { BoxDimensionInput } from './BoxDimensionInput';

export const fieldKeyInputId = (fieldId: string): string => `field-key-${fieldId}`;

const focusElement = (element: HTMLElement | null) => element?.focus();

type FieldEditorRowProps = {
  field: TemplateField;
  keyProblem: FieldKeyProblem | undefined;
  isSelected: boolean;
  shouldFocusKey: boolean;
  imageSize: ImageSize;
  actions: FieldEditorActions;
};

export const FieldEditorRow = ({
  field,
  keyProblem,
  isSelected,
  shouldFocusKey,
  imageSize,
  actions,
}: FieldEditorRowProps) => {
  const { t } = useTranslation('templates');
  const keyInputId = fieldKeyInputId(field.id);
  const keyHintId = `${keyInputId}-hint`;
  const keyErrorId = `${keyInputId}-error`;
  const idPrefix = `field-${field.id}`;

  const selectThisField = () => actions.select(field.id);

  const changeFieldType = (rawValue: string) => {
    const parsed = fieldTypeSchema.safeParse(rawValue);
    if (parsed.success) {
      actions.update(field.id, { fieldType: parsed.data });
    }
  };

  return (
    <li className={`field-row field-type--${field.fieldType}${isSelected ? ' field-row--selected' : ''}`}>
      <fieldset className="field-row__fieldset">
        <legend className="field-row__legend">{field.label || field.key}</legend>
        <div className="field-row__grid">
          <div className="form-control">
            <label htmlFor={keyInputId}>{t('field.key')}</label>
            <input
              id={keyInputId}
              ref={shouldFocusKey ? focusElement : undefined}
              className="input input--mono"
              value={field.key}
              maxLength={FIELD_KEY_MAX_LENGTH}
              spellCheck={false}
              autoComplete="off"
              aria-invalid={keyProblem ? true : undefined}
              aria-describedby={keyProblem ? `${keyHintId} ${keyErrorId}` : keyHintId}
              onFocus={selectThisField}
              onChange={(event) => actions.update(field.id, { key: event.target.value })}
            />
            <p id={keyHintId} className="hint">
              {t('field.keyHint')}
            </p>
            {keyProblem && (
              <p id={keyErrorId} className="field-error">
                {t(`validation.key.${keyProblem}`)}
              </p>
            )}
          </div>
          <div className="form-control">
            <label htmlFor={`${idPrefix}-label`}>{t('field.label')}</label>
            <input
              id={`${idPrefix}-label`}
              className="input"
              value={field.label}
              maxLength={FIELD_LABEL_MAX_LENGTH}
              onFocus={selectThisField}
              onChange={(event) => actions.update(field.id, { label: event.target.value })}
            />
          </div>
          <div className="form-control">
            <label htmlFor={`${idPrefix}-type`}>{t('field.type')}</label>
            <select
              id={`${idPrefix}-type`}
              className="select"
              value={field.fieldType}
              onFocus={selectThisField}
              onChange={(event) => changeFieldType(event.target.value)}
            >
              {FIELD_TYPES.map((fieldType) => (
                <option key={fieldType} value={fieldType}>
                  {t(`common:fieldTypes.${fieldType}`)}
                </option>
              ))}
            </select>
          </div>
        </div>
        {field.fieldType === 'choice' ? (
          <ChoiceOptionsEditor field={field} imageSize={imageSize} actions={actions} />
        ) : (
          <details className="field-row__position">
            <summary>{t('field.position')}</summary>
            <div className="field-row__position-grid">
              {BOX_DIMENSIONS.map((dimension) => (
                <BoxDimensionInput
                  key={dimension}
                  id={`${idPrefix}-${dimension}`}
                  label={t(`field.box.${dimension}`)}
                  value={field.box[dimension]}
                  onFocus={selectThisField}
                  onCommit={(value) =>
                    actions.setBox(field.id, setBoxDimension(field.box, dimension, value, imageSize))
                  }
                />
              ))}
            </div>
          </details>
        )}
        <button
          type="button"
          className="button button--ghost-danger button--small"
          onClick={() => actions.remove(field.id)}
        >
          <Trash2 aria-hidden="true" className="icon icon--sm" />
          {t('field.remove', { name: field.label || field.key })}
        </button>
      </fieldset>
    </li>
  );
};
