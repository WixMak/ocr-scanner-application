import { act, renderHook } from '@testing-library/react';
import { accountTypeField, nameField, signatureField } from '../../test/fixtures';
import { useFieldEditor } from './useFieldEditor';

describe('useFieldEditor', () => {
  it('shows the page of the selected field and stays there for an unknown field', () => {
    const { result } = renderHook(() => useFieldEditor([nameField, signatureField]));

    act(() => result.current.actions.select(signatureField.id));
    expect(result.current.currentPageIndex).toBe(1);

    act(() => result.current.actions.select('removed-field'));
    expect(result.current.currentPageIndex).toBe(1);
  });
});

const renderEditorWithChoice = () => renderHook(() => useFieldEditor([accountTypeField]));

describe('useFieldEditor — choice fields', () => {
  it('keeps the existing options when Choice is chosen again', () => {
    const { result } = renderEditorWithChoice();

    act(() => result.current.actions.update(accountTypeField.id, { fieldType: 'choice' }));

    expect(result.current.fields[0]?.options).toEqual(accountTypeField.options);
  });

  it('never removes the last remaining option', () => {
    const { result } = renderEditorWithChoice();
    const [personal, joint] = accountTypeField.options;

    act(() => {
      result.current.actions.removeOption(accountTypeField.id, personal?.id ?? '');
      result.current.actions.removeOption(accountTypeField.id, joint?.id ?? '');
    });

    expect(result.current.fields[0]?.options).toEqual([joint]);
    expect(result.current.fields[0]?.box).toEqual(joint?.box);
  });
});
