import { Plus, Trash2 } from 'lucide-react';
import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ChoiceOption, TemplateField } from '../../api/schemas';
import { BOX_DIMENSIONS, setBoxDimension, type ImageSize } from './boxGeometry';
import { BoxDimensionInput } from './BoxDimensionInput';
import { FIELD_LABEL_MAX_LENGTH } from './templateValidation';
import type { FieldEditorActions } from './useFieldEditor';

const focusElement = (element: HTMLElement | null) => element?.focus();

type ChoiceOptionsEditorProps = {
  field: TemplateField;
  imageSize: ImageSize;
  actions: FieldEditorActions;
};

export const ChoiceOptionsEditor = ({ field, imageSize, actions }: ChoiceOptionsEditorProps) => {
  const { t } = useTranslation('templates');
  const addButtonRef = useRef<HTMLButtonElement>(null);
  const [addedOptionId, setAddedOptionId] = useState<string | null>(null);
  const canRemoveOptions = field.options.length > 1;
  const hintId = `field-${field.id}-options-hint`;

  const selectThisField = () => actions.select(field.id);

  const addOption = () => {
    const optionId = crypto.randomUUID();
    actions.addOption(field.id, { optionId, imageSize });
    setAddedOptionId(optionId);
  };

  const removeOption = (optionId: string) => {
    actions.removeOption(field.id, optionId);
    addButtonRef.current?.focus();
  };

  const renderOption = (option: ChoiceOption, optionIndex: number) => {
    const optionName = option.label || t('field.optionFallback', { number: optionIndex + 1 });
    const idPrefix = `option-${option.id}`;
    return (
      <li key={option.id} className="choice-option">
        <fieldset className="field-row__fieldset">
          <legend className="choice-option__legend">{optionName}</legend>
          <div className="form-control">
            <label htmlFor={`${idPrefix}-label`}>{t('field.optionText')}</label>
            <input
              id={`${idPrefix}-label`}
              ref={option.id === addedOptionId ? focusElement : undefined}
              className="input"
              value={option.label}
              maxLength={FIELD_LABEL_MAX_LENGTH}
              onFocus={selectThisField}
              onChange={(event) => actions.renameOption(field.id, option.id, event.target.value)}
            />
          </div>
          <details className="field-row__position">
            <summary>{t('field.position')}</summary>
            <div className="field-row__position-grid">
              {BOX_DIMENSIONS.map((dimension) => (
                <BoxDimensionInput
                  key={dimension}
                  id={`${idPrefix}-${dimension}`}
                  label={t(`field.box.${dimension}`)}
                  value={option.box[dimension]}
                  onFocus={selectThisField}
                  onCommit={(value) =>
                    actions.setOptionBox(
                      field.id,
                      option.id,
                      setBoxDimension(option.box, dimension, value, imageSize),
                    )
                  }
                />
              ))}
            </div>
          </details>
          {canRemoveOptions && (
            <button
              type="button"
              className="button button--ghost-danger button--small"
              onClick={() => removeOption(option.id)}
            >
              <Trash2 aria-hidden="true" className="icon icon--sm" />
              {t('field.removeOption', { name: optionName })}
            </button>
          )}
        </fieldset>
      </li>
    );
  };

  return (
    <fieldset className="choice-options" aria-describedby={hintId}>
      <legend className="choice-options__legend">{t('field.options')}</legend>
      <p id={hintId} className="hint">
        {t('field.optionsHint')}
      </p>
      <ol className="choice-options__list">{field.options.map(renderOption)}</ol>
      <button
        ref={addButtonRef}
        type="button"
        className="button button--secondary button--small"
        onClick={addOption}
      >
        <Plus aria-hidden="true" className="icon icon--sm" />
        {t('field.addOption')}
      </button>
    </fieldset>
  );
};
