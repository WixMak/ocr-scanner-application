import { useTranslation } from 'react-i18next';
import { StatusBadge } from '../../components/StatusBadge';
import { extractedValueInputId, type ExtractedFieldView } from './extractionView';

type ExtractedFieldRowProps = {
  field: ExtractedFieldView;
  formatConfidence: (confidence: number) => string;
  onValueChange: (fieldId: string, value: string) => void;
};

export const ExtractedFieldRow = ({ field, formatConfidence, onValueChange }: ExtractedFieldRowProps) => {
  const { t } = useTranslation('extraction');
  const inputId = extractedValueInputId(field.fieldId);
  const detailsId = `${inputId}-details`;
  const confidenceText =
    field.status === 'empty' ? t('result.notApplicable') : formatConfidence(field.confidence);

  return (
    <li className={`extracted-row extracted-row--${field.displayStatus}`}>
      <div className="extracted-row__header">
        <label htmlFor={inputId} className="extracted-row__label">
          {field.label || field.key}
        </label>
        <StatusBadge status={field.displayStatus} />
      </div>
      <input
        id={inputId}
        className="input"
        value={field.displayValue}
        aria-describedby={detailsId}
        onChange={(event) => onValueChange(field.fieldId, event.target.value)}
      />
      <p id={detailsId} className="extracted-row__meta">
        <code className="extracted-row__key">{field.key}</code>
        <span>{t('result.confidence', { confidence: confidenceText })}</span>
      </p>
      {field.readings.length > 0 && (
        <details className="extracted-row__readings">
          <summary>{t('result.readingsSummary', { count: field.readings.length })}</summary>
          <table className="readings-table">
            <thead>
              <tr>
                <th scope="col">{t('result.readingsColumns.engine')}</th>
                <th scope="col">{t('result.readingsColumns.text')}</th>
                <th scope="col">{t('result.readingsColumns.confidence')}</th>
              </tr>
            </thead>
            <tbody>
              {field.readings.map((reading) => (
                <tr key={reading.engine}>
                  <td>{reading.engine}</td>
                  <td>{reading.text || t('result.noValue')}</td>
                  <td className="data-table__numeric">{formatConfidence(reading.confidence)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </li>
  );
};
