import { useTranslation } from 'react-i18next';
import { toOverlayPosition, type ImageSize } from '../templates/boxGeometry';
import { extractedValueInputId, type ExtractedFieldView } from './extractionView';

type ResultFieldBoxProps = {
  field: ExtractedFieldView;
  imageSize: ImageSize;
};

const focusValueInput = (fieldId: string) => {
  document.getElementById(extractedValueInputId(fieldId))?.focus();
};

export const ResultFieldBox = ({ field, imageSize }: ResultFieldBoxProps) => {
  const { t } = useTranslation('extraction');
  const statusText = t(`common:fieldStatus.${field.displayStatus}`);
  const valueText = field.displayValue || t('result.noValue');

  return (
    <button
      type="button"
      className={`result-box result-box--${field.displayStatus}`}
      style={toOverlayPosition(field.box, imageSize)}
      aria-label={t('result.boxLabel', {
        label: field.label || field.key,
        value: valueText,
        status: statusText,
      })}
      onClick={() => focusValueInput(field.fieldId)}
    />
  );
};
