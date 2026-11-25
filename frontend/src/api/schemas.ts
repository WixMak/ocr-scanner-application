import { z } from 'zod';

export const FIELD_TYPES = ['text', 'number', 'date', 'choice'] as const;
export const FIELD_STATUSES = ['confirmed', 'review', 'empty'] as const;

export const fieldTypeSchema = z.enum(FIELD_TYPES);
export const fieldStatusSchema = z.enum(FIELD_STATUSES);

export const boundingBoxSchema = z.object({
  x: z.number().int().nonnegative(),
  y: z.number().int().nonnegative(),
  width: z.number().int().positive(),
  height: z.number().int().positive(),
});

export const pageSizeSchema = z.object({
  imageWidth: z.number().int().positive(),
  imageHeight: z.number().int().positive(),
});

export const choiceOptionSchema = z.object({
  id: z.string(),
  label: z.string(),
  box: boundingBoxSchema,
});

export const templateFieldSchema = z.object({
  id: z.string(),
  key: z.string(),
  label: z.string(),
  fieldType: fieldTypeSchema,
  pageIndex: z.number().int().nonnegative(),
  box: boundingBoxSchema,
  options: z.array(choiceOptionSchema),
});

export const templateDraftSchema = z.object({
  draftId: z.string(),
  pages: z.array(pageSizeSchema).min(1),
  fields: z.array(templateFieldSchema),
});

export const templateSchema = z.object({
  id: z.string(),
  name: z.string(),
  pages: z.array(pageSizeSchema).min(1),
  fields: z.array(templateFieldSchema),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export const templateSummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  fieldCount: z.number().int().nonnegative(),
  updatedAt: z.string(),
});

export const engineReadingSchema = z.object({
  engine: z.string(),
  text: z.string(),
  confidence: z.number(),
});

export const extractedFieldSchema = z.object({
  fieldId: z.string(),
  key: z.string(),
  label: z.string(),
  fieldType: fieldTypeSchema,
  pageIndex: z.number().int().nonnegative(),
  box: boundingBoxSchema,
  value: z.string(),
  confidence: z.number(),
  status: fieldStatusSchema,
  readings: z.array(engineReadingSchema),
});

export const resultPageSchema = pageSizeSchema.extend({
  pageIndex: z.number().int().nonnegative(),
  scanPageNumber: z.number().int().positive(),
  imageDataUrl: z.string().startsWith('data:image/'),
  isAligned: z.boolean(),
});

export const extractionResultSchema = z.object({
  templateId: z.string(),
  templateName: z.string(),
  pages: z.array(resultPageSchema).min(1),
  values: z.record(z.string(), z.string()),
  fields: z.array(extractedFieldSchema),
});

const engineAvailabilitySchema = z.object({
  model: z.string(),
  isAvailable: z.boolean(),
});

export const healthStatusSchema = z.object({
  isOllamaReachable: z.boolean(),
  fastModel: engineAvailabilitySchema,
  accurateModel: engineAvailabilitySchema,
});

export const apiErrorBodySchema = z.object({
  code: z.string(),
  message: z.string(),
  pageNumbers: z.array(z.number().int().positive()).optional(),
});

export type FieldType = z.infer<typeof fieldTypeSchema>;
export type FieldStatus = z.infer<typeof fieldStatusSchema>;
export type BoundingBox = z.infer<typeof boundingBoxSchema>;
export type PageSize = z.infer<typeof pageSizeSchema>;
export type ChoiceOption = z.infer<typeof choiceOptionSchema>;
export type TemplateField = z.infer<typeof templateFieldSchema>;
export type TemplateDraft = z.infer<typeof templateDraftSchema>;
export type Template = z.infer<typeof templateSchema>;
export type TemplateSummary = z.infer<typeof templateSummarySchema>;
export type EngineReading = z.infer<typeof engineReadingSchema>;
export type ExtractedField = z.infer<typeof extractedFieldSchema>;
export type ResultPage = z.infer<typeof resultPageSchema>;
export type ExtractionResult = z.infer<typeof extractionResultSchema>;
export type HealthStatus = z.infer<typeof healthStatusSchema>;

export type TemplateInput = Pick<Template, 'name' | 'fields'>;
