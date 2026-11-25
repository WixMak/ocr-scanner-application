import { nameField, phoneField } from '../../test/fixtures';
import { isTemplateValid, suggestUnusedKey, validateTemplate } from './templateValidation';

describe('validateTemplate', () => {
  it('accepts a named template with unique valid keys', () => {
    const validation = validateTemplate('MPF', [nameField, phoneField]);

    expect(isTemplateValid(validation)).toBe(true);
  });

  it('reports a blank name', () => {
    const validation = validateTemplate('   ', [nameField]);

    expect(validation.isNameMissing).toBe(true);
    expect(isTemplateValid(validation)).toBe(false);
  });

  it('reports missing, invalid and duplicate keys per field', () => {
    const fields = [
      { ...nameField, id: 'a', key: '' },
      { ...nameField, id: 'b', key: 'Full Name' },
      { ...nameField, id: 'c', key: 'phone' },
      { ...phoneField, id: 'd', key: 'phone' },
    ];

    const validation = validateTemplate('MPF', fields);

    expect(Object.fromEntries(validation.keyProblems)).toEqual({
      a: 'required',
      b: 'invalid',
      c: 'duplicate',
      d: 'duplicate',
    });
  });
});

describe('suggestUnusedKey', () => {
  it('numbers new fields after the existing ones and skips taken keys', () => {
    expect(suggestUnusedKey([])).toBe('field_1');
    expect(suggestUnusedKey([nameField, { ...phoneField, key: 'field_3' }])).toBe('field_4');
  });
});
