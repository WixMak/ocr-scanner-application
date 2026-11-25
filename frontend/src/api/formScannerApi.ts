import { z } from 'zod';
import { API_BASE_PATH, jsonRequestInit, requestJson, requestWithoutContent } from './client';
import {
  extractionResultSchema,
  healthStatusSchema,
  templateDraftSchema,
  templateSchema,
  templateSummarySchema,
  type ExtractionResult,
  type HealthStatus,
  type Template,
  type TemplateDraft,
  type TemplateInput,
  type TemplateSummary,
} from './schemas';

const TEMPLATES_PATH = '/templates';

const toUploadBody = (file: File, extraFields: Record<string, string> = {}): FormData => {
  const body = new FormData();
  body.append('file', file);
  Object.entries(extraFields).forEach(([name, value]) => body.append(name, value));
  return body;
};

export const createTemplateDraft = (file: File): Promise<TemplateDraft> =>
  requestJson(`${TEMPLATES_PATH}/drafts`, templateDraftSchema, {
    method: 'POST',
    body: toUploadBody(file),
  });

export const getDraftImageUrl = (draftId: string, pageIndex: number): string =>
  `${API_BASE_PATH}${TEMPLATES_PATH}/drafts/${encodeURIComponent(draftId)}/pages/${pageIndex}/image`;

export const getTemplateImageUrl = (templateId: string, pageIndex: number): string =>
  `${API_BASE_PATH}${TEMPLATES_PATH}/${encodeURIComponent(templateId)}/pages/${pageIndex}/image`;

export const listTemplates = (): Promise<TemplateSummary[]> =>
  requestJson(TEMPLATES_PATH, z.array(templateSummarySchema));

export const getTemplate = (templateId: string): Promise<Template> =>
  requestJson(`${TEMPLATES_PATH}/${encodeURIComponent(templateId)}`, templateSchema);

export const createTemplate = (draftId: string, input: TemplateInput): Promise<Template> =>
  requestJson(TEMPLATES_PATH, templateSchema, jsonRequestInit('POST', { ...input, draftId }));

export const updateTemplate = (templateId: string, input: TemplateInput): Promise<Template> =>
  requestJson(
    `${TEMPLATES_PATH}/${encodeURIComponent(templateId)}`,
    templateSchema,
    jsonRequestInit('PUT', input),
  );

export const deleteTemplate = (templateId: string): Promise<void> =>
  requestWithoutContent(`${TEMPLATES_PATH}/${encodeURIComponent(templateId)}`, {
    method: 'DELETE',
  });

export const extractFormValues = (templateId: string, file: File): Promise<ExtractionResult> =>
  requestJson('/extractions', extractionResultSchema, {
    method: 'POST',
    body: toUploadBody(file, { templateId }),
  });

export const getHealth = (): Promise<HealthStatus> => requestJson('/health', healthStatusSchema);
