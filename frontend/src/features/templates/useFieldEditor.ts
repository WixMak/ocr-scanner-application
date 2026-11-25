import { useReducer } from 'react';
import type { BoundingBox, ChoiceOption, FieldType, TemplateField } from '../../api/schemas';
import { createDefaultBox, enclosingBox, moveBox, type ImageSize } from './boxGeometry';
import { suggestUnusedKey } from './templateValidation';

export type EditableFieldProperties = Pick<TemplateField, 'key' | 'label' | 'fieldType'>;

export type NewOption = { optionId: string; imageSize: ImageSize };

type FieldEditorState = {
  fields: TemplateField[];
  selectedFieldId: string | null;
  addedFieldId: string | null;
  currentPageIndex: number;
};

type FieldEditorAction =
  | { type: 'select'; fieldId: string }
  | { type: 'showPage'; pageIndex: number }
  | { type: 'update'; fieldId: string; changes: Partial<EditableFieldProperties> }
  | { type: 'setBox'; fieldId: string; box: BoundingBox }
  | { type: 'add'; imageSize: ImageSize }
  | { type: 'remove'; fieldId: string }
  | { type: 'addOption'; fieldId: string; newOption: NewOption }
  | { type: 'renameOption'; fieldId: string; optionId: string; label: string }
  | { type: 'setOptionBox'; fieldId: string; optionId: string; box: BoundingBox }
  | { type: 'removeOption'; fieldId: string; optionId: string };

const replaceField = (
  fields: TemplateField[],
  fieldId: string,
  change: (field: TemplateField) => TemplateField,
): TemplateField[] => fields.map((field) => (field.id === fieldId ? change(field) : field));

const withOptions = (field: TemplateField, options: ChoiceOption[]): TemplateField => ({
  ...field,
  options,
  box: enclosingBox(options.map((option) => option.box)),
});

const replaceOption = (
  field: TemplateField,
  optionId: string,
  change: (option: ChoiceOption) => ChoiceOption,
): TemplateField =>
  withOptions(
    field,
    field.options.map((option) => (option.id === optionId ? change(option) : option)),
  );

const changeFieldType = (field: TemplateField, fieldType: FieldType): TemplateField => {
  if (fieldType !== 'choice') {
    return { ...field, fieldType, options: [] };
  }
  if (field.fieldType === 'choice') {
    return field;
  }
  const firstOption = { id: crypto.randomUUID(), label: field.label, box: field.box };
  return { ...field, fieldType, options: [firstOption] };
};

const updateField = (
  field: TemplateField,
  { fieldType, ...otherChanges }: Partial<EditableFieldProperties>,
): TemplateField => {
  const updated = { ...field, ...otherChanges };
  return fieldType ? changeFieldType(updated, fieldType) : updated;
};

const addOption = (field: TemplateField, { optionId, imageSize }: NewOption): TemplateField => {
  const lastBox = field.options.at(-1)?.box ?? field.box;
  const nextBox = moveBox(lastBox, { deltaX: lastBox.width * 2, deltaY: 0 }, imageSize);
  return withOptions(field, [...field.options, { id: optionId, label: '', box: nextBox }]);
};

const removeOption = (field: TemplateField, optionId: string): TemplateField => {
  const remainingOptions = field.options.filter((option) => option.id !== optionId);
  return remainingOptions.length > 0 ? withOptions(field, remainingOptions) : field;
};

const fieldEditorReducer = (
  state: FieldEditorState,
  action: FieldEditorAction,
): FieldEditorState => {
  switch (action.type) {
    case 'select': {
      const selectedField = state.fields.find((field) => field.id === action.fieldId);
      return {
        ...state,
        selectedFieldId: action.fieldId,
        currentPageIndex: selectedField?.pageIndex ?? state.currentPageIndex,
      };
    }
    case 'showPage':
      return { ...state, currentPageIndex: action.pageIndex };
    case 'update':
      return {
        ...state,
        fields: replaceField(state.fields, action.fieldId, (field) =>
          updateField(field, action.changes),
        ),
      };
    case 'setBox':
      return {
        ...state,
        fields: replaceField(state.fields, action.fieldId, (field) => ({
          ...field,
          box: action.box,
        })),
      };
    case 'add': {
      const newField: TemplateField = {
        id: crypto.randomUUID(),
        key: suggestUnusedKey(state.fields),
        label: '',
        fieldType: 'text',
        pageIndex: state.currentPageIndex,
        box: createDefaultBox(action.imageSize),
        options: [],
      };
      return {
        ...state,
        fields: [...state.fields, newField],
        selectedFieldId: newField.id,
        addedFieldId: newField.id,
      };
    }
    case 'remove':
      return {
        ...state,
        fields: state.fields.filter((field) => field.id !== action.fieldId),
        selectedFieldId: state.selectedFieldId === action.fieldId ? null : state.selectedFieldId,
        addedFieldId: state.addedFieldId === action.fieldId ? null : state.addedFieldId,
      };
    case 'addOption':
      return {
        ...state,
        fields: replaceField(state.fields, action.fieldId, (field) =>
          addOption(field, action.newOption),
        ),
      };
    case 'renameOption':
      return {
        ...state,
        fields: replaceField(state.fields, action.fieldId, (field) =>
          replaceOption(field, action.optionId, (option) => ({ ...option, label: action.label })),
        ),
      };
    case 'setOptionBox':
      return {
        ...state,
        fields: replaceField(state.fields, action.fieldId, (field) =>
          replaceOption(field, action.optionId, (option) => ({ ...option, box: action.box })),
        ),
      };
    case 'removeOption':
      return {
        ...state,
        fields: replaceField(state.fields, action.fieldId, (field) =>
          removeOption(field, action.optionId),
        ),
      };
  }
};

export type FieldEditorActions = {
  select: (fieldId: string) => void;
  update: (fieldId: string, changes: Partial<EditableFieldProperties>) => void;
  setBox: (fieldId: string, box: BoundingBox) => void;
  remove: (fieldId: string) => void;
  addOption: (fieldId: string, newOption: NewOption) => void;
  renameOption: (fieldId: string, optionId: string, label: string) => void;
  setOptionBox: (fieldId: string, optionId: string, box: BoundingBox) => void;
  removeOption: (fieldId: string, optionId: string) => void;
};

export const useFieldEditor = (initialFields: TemplateField[]) => {
  const [state, dispatch] = useReducer(fieldEditorReducer, {
    fields: initialFields,
    selectedFieldId: null,
    addedFieldId: null,
    currentPageIndex: 0,
  });

  const actions: FieldEditorActions = {
    select: (fieldId) => dispatch({ type: 'select', fieldId }),
    update: (fieldId, changes) => dispatch({ type: 'update', fieldId, changes }),
    setBox: (fieldId, box) => dispatch({ type: 'setBox', fieldId, box }),
    remove: (fieldId) => dispatch({ type: 'remove', fieldId }),
    addOption: (fieldId, newOption) => dispatch({ type: 'addOption', fieldId, newOption }),
    renameOption: (fieldId, optionId, label) =>
      dispatch({ type: 'renameOption', fieldId, optionId, label }),
    setOptionBox: (fieldId, optionId, box) =>
      dispatch({ type: 'setOptionBox', fieldId, optionId, box }),
    removeOption: (fieldId, optionId) => dispatch({ type: 'removeOption', fieldId, optionId }),
  };
  const addField = (imageSize: ImageSize) => dispatch({ type: 'add', imageSize });
  const showPage = (pageIndex: number) => dispatch({ type: 'showPage', pageIndex });

  return { ...state, actions, addField, showPage };
};
