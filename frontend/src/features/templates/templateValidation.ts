import type { TemplateField } from '../../api/schemas';

export const FIELD_KEY_PATTERN = /^[a-z][a-z0-9_]*$/;
export const FIELD_KEY_MAX_LENGTH = 64;
export const FIELD_LABEL_MAX_LENGTH = 200;
export const TEMPLATE_NAME_MAX_LENGTH = 120;

export type FieldKeyProblem = 'required' | 'invalid' | 'duplicate';

export type TemplateValidation = {
  isNameMissing: boolean;
  keyProblems: Map<string, FieldKeyProblem>;
};

const findKeyProblem = (key: string, keyCounts: Map<string, number>): FieldKeyProblem | null => {
  if (!key) {
    return 'required';
  }
  if (!FIELD_KEY_PATTERN.test(key)) {
    return 'invalid';
  }
  return (keyCounts.get(key) ?? 0) > 1 ? 'duplicate' : null;
};

const countKeys = (fields: TemplateField[]): Map<string, number> => {
  const keyCounts = new Map<string, number>();
  fields.forEach((field) => keyCounts.set(field.key, (keyCounts.get(field.key) ?? 0) + 1));
  return keyCounts;
};

export const validateTemplate = (name: string, fields: TemplateField[]): TemplateValidation => {
  const keyCounts = countKeys(fields);
  const keyProblems = new Map<string, FieldKeyProblem>();
  fields.forEach((field) => {
    const problem = findKeyProblem(field.key, keyCounts);
    if (problem) {
      keyProblems.set(field.id, problem);
    }
  });
  return { isNameMissing: name.trim() === '', keyProblems };
};

export const isTemplateValid = (validation: TemplateValidation): boolean =>
  !validation.isNameMissing && validation.keyProblems.size === 0;

export const suggestUnusedKey = (fields: TemplateField[]): string => {
  const usedKeys = new Set(fields.map((field) => field.key));
  let number = fields.length + 1;
  while (usedKeys.has(`field_${number}`)) {
    number += 1;
  }
  return `field_${number}`;
};
