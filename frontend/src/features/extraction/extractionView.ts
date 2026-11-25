import type { ExtractedField, ExtractionResult, FieldStatus } from '../../api/schemas';
import type { DisplayStatus } from '../../components/StatusBadge';

export type EditedValues = Readonly<Record<string, string>>;

export type ExtractedFieldView = ExtractedField & {
  displayValue: string;
  displayStatus: DisplayStatus;
};

export type ExtractionJson = {
  templateId: string;
  templateName: string;
  values: Record<string, string>;
  fields: {
    key: string;
    label: string;
    value: string;
    status: DisplayStatus;
    confidence: number;
  }[];
};

export const toFieldViews = (
  result: ExtractionResult,
  editedValues: EditedValues,
): ExtractedFieldView[] =>
  result.fields.map((field) => {
    const editedValue = editedValues[field.fieldId];
    const isEdited = editedValue !== undefined && editedValue !== field.value;
    return {
      ...field,
      displayValue: isEdited ? editedValue : field.value,
      displayStatus: isEdited ? 'edited' : field.status,
    };
  });

export const buildExtractionJson = (
  result: ExtractionResult,
  fieldViews: ExtractedFieldView[],
): ExtractionJson => ({
  templateId: result.templateId,
  templateName: result.templateName,
  values: Object.fromEntries(fieldViews.map((field) => [field.key, field.displayValue])),
  fields: fieldViews.map((field) => ({
    key: field.key,
    label: field.label,
    value: field.displayValue,
    status: field.displayStatus,
    confidence: field.confidence,
  })),
});

export const countByStatus = (fields: ExtractedField[]): Record<FieldStatus, number> => {
  const counts: Record<FieldStatus, number> = { confirmed: 0, review: 0, empty: 0 };
  fields.forEach((field) => {
    counts[field.status] += 1;
  });
  return counts;
};

export const extractedValueInputId = (fieldId: string): string => `extracted-value-${fieldId}`;
