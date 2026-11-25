import type {
  ExtractionResult,
  HealthStatus,
  Template,
  TemplateDraft,
  TemplateField,
  TemplateSummary,
} from '../api/schemas';

export const TEMPLATE_ID = 'a'.repeat(32);
export const DRAFT_ID = 'b'.repeat(32);
export const IMAGE_SIZE = { width: 1654, height: 2339 };
export const PAGE_SIZE = { imageWidth: IMAGE_SIZE.width, imageHeight: IMAGE_SIZE.height };
export const RESULT_IMAGE_DATA_URL = 'data:image/jpeg;base64,AAAA';
export const SECOND_RESULT_IMAGE_DATA_URL = 'data:image/jpeg;base64,BBBB';

export const nameField: TemplateField = {
  id: 'field-name',
  key: 'full_name',
  label: '姓名 Full Name',
  fieldType: 'text',
  pageIndex: 0,
  box: { x: 384, y: 233, width: 1147, height: 75 },
  options: [],
};

export const phoneField: TemplateField = {
  id: 'field-phone',
  key: 'phone',
  label: '电话 Phone',
  fieldType: 'number',
  pageIndex: 0,
  box: { x: 328, y: 482, width: 1203, height: 86 },
  options: [],
};

export const accountTypeField: TemplateField = {
  id: 'field-account-type',
  key: 'bank_account_type',
  label: 'Bank Account Type 銀行帳戶類別',
  fieldType: 'choice',
  pageIndex: 0,
  box: { x: 200, y: 700, width: 434, height: 34 },
  options: [
    {
      id: 'option-personal',
      label: 'Personal 個人',
      box: { x: 200, y: 700, width: 34, height: 34 },
    },
    { id: 'option-joint', label: 'Joint 聯名', box: { x: 600, y: 700, width: 34, height: 34 } },
  ],
};

export const draft: TemplateDraft = {
  draftId: DRAFT_ID,
  pages: [PAGE_SIZE],
  fields: [nameField, phoneField],
};

export const signatureField: TemplateField = {
  id: 'field-signature',
  key: 'signature',
  label: 'Signature',
  fieldType: 'text',
  pageIndex: 1,
  box: { x: 100, y: 1900, width: 800, height: 120 },
  options: [],
};

export const draftWithChoice: TemplateDraft = {
  draftId: DRAFT_ID,
  pages: [PAGE_SIZE],
  fields: [nameField, accountTypeField],
};

export const twoPageDraft: TemplateDraft = {
  draftId: DRAFT_ID,
  pages: [PAGE_SIZE, PAGE_SIZE],
  fields: [nameField, phoneField, signatureField],
};

export const template: Template = {
  id: TEMPLATE_ID,
  name: 'MPF Enrolment',
  pages: [PAGE_SIZE],
  fields: [nameField, phoneField],
  createdAt: '2026-11-20T08:00:00Z',
  updatedAt: '2026-11-21T09:30:00Z',
};

export const templateSummary: TemplateSummary = {
  id: TEMPLATE_ID,
  name: template.name,
  fieldCount: 2,
  updatedAt: template.updatedAt,
};

export const healthyStatus: HealthStatus = {
  isOllamaReachable: true,
  fastModel: { model: 'qwen3-vl:4b', isAvailable: true },
  accurateModel: { model: 'qwen3-vl:8b', isAvailable: true },
};

export const extractionResult: ExtractionResult = {
  templateId: TEMPLATE_ID,
  templateName: template.name,
  pages: [
    {
      ...PAGE_SIZE,
      pageIndex: 0,
      scanPageNumber: 1,
      imageDataUrl: RESULT_IMAGE_DATA_URL,
      isAligned: true,
    },
  ],
  values: { full_name: '陈大文', phone: '9123 4567', signed_date: '' },
  fields: [
    {
      fieldId: nameField.id,
      key: nameField.key,
      label: nameField.label,
      fieldType: 'text',
      pageIndex: 0,
      box: nameField.box,
      value: '陈大文',
      confidence: 0.98,
      status: 'confirmed',
      readings: [
        { engine: 'paddleocr', text: '陈大文', confidence: 0.97 },
        { engine: 'qwen-fast', text: '陈大文', confidence: 0.98 },
      ],
    },
    {
      fieldId: phoneField.id,
      key: phoneField.key,
      label: phoneField.label,
      fieldType: 'number',
      pageIndex: 0,
      box: phoneField.box,
      value: '9123 4567',
      confidence: 0.62,
      status: 'review',
      readings: [
        { engine: 'paddleocr', text: '9123 4561', confidence: 0.7 },
        { engine: 'qwen-fast', text: '9123 4567', confidence: 0.9 },
        { engine: 'qwen-accurate', text: '9123 4567', confidence: 0.62 },
      ],
    },
    {
      fieldId: 'field-signed',
      key: 'signed_date',
      label: '',
      fieldType: 'date',
      pageIndex: 0,
      box: { x: 484, y: 1240, width: 1124, height: 72 },
      value: '',
      confidence: 1,
      status: 'empty',
      readings: [],
    },
  ],
};

export const twoPageExtractionResult: ExtractionResult = {
  ...extractionResult,
  pages: [
    {
      ...PAGE_SIZE,
      pageIndex: 0,
      scanPageNumber: 1,
      imageDataUrl: RESULT_IMAGE_DATA_URL,
      isAligned: true,
    },
    {
      ...PAGE_SIZE,
      pageIndex: 1,
      scanPageNumber: 2,
      imageDataUrl: SECOND_RESULT_IMAGE_DATA_URL,
      isAligned: false,
    },
  ],
  fields: extractionResult.fields.map((field) =>
    field.key === 'signed_date' ? { ...field, pageIndex: 1 } : field,
  ),
};

export const reorderedScanExtractionResult: ExtractionResult = {
  ...extractionResult,
  pages: [
    {
      ...PAGE_SIZE,
      pageIndex: 0,
      scanPageNumber: 2,
      imageDataUrl: RESULT_IMAGE_DATA_URL,
      isAligned: false,
    },
    {
      ...PAGE_SIZE,
      pageIndex: 2,
      scanPageNumber: 1,
      imageDataUrl: SECOND_RESULT_IMAGE_DATA_URL,
      isAligned: true,
    },
  ],
  fields: extractionResult.fields.map((field) =>
    field.key === 'signed_date' ? { ...field, pageIndex: 2 } : field,
  ),
};

export const makeFile = (name: string, type: string, sizeInBytes = 4): File => {
  const file = new File(['x'.repeat(Math.min(sizeInBytes, 16))], name, { type });
  Object.defineProperty(file, 'size', { value: sizeInBytes });
  return file;
};
