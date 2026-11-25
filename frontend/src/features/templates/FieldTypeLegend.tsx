import { useTranslation } from 'react-i18next';
import { FIELD_TYPES } from '../../api/schemas';
import { FieldTypeIcon } from './FieldTypeIcon';

export const FieldTypeLegend = () => {
  const { t } = useTranslation('templates');

  return (
    <ul className="field-type-legend" aria-label={t('editor.typeLegend')}>
      {FIELD_TYPES.map((fieldType) => (
        <li key={fieldType} className={`field-type-legend__item field-type--${fieldType}`}>
          <span className="field-type-legend__swatch" aria-hidden="true">
            <FieldTypeIcon fieldType={fieldType} className="icon--xs" />
          </span>
          {t(`common:fieldTypes.${fieldType}`)}
        </li>
      ))}
    </ul>
  );
};
