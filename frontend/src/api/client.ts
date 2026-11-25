import type { z } from 'zod';
import { apiErrorBodySchema } from './schemas';

export const API_BASE_PATH = '/api';
export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

export const CLIENT_ERROR_CODES = {
  network: 'network_error',
  invalidResponse: 'invalid_response',
  unknown: 'unknown_error',
} as const;

type ApiErrorDetails = {
  code: string;
  status: number;
  message: string;
  pageNumbers?: readonly number[];
};

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly pageNumbers: readonly number[];

  constructor({ code, status, message, pageNumbers = [] }: ApiErrorDetails) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.pageNumbers = pageNumbers;
  }
}

const sendRequest = async (path: string, init?: RequestInit): Promise<Response> => {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_PATH}${path}`, init);
  } catch {
    throw new ApiError({
      code: CLIENT_ERROR_CODES.network,
      status: 0,
      message: 'The server could not be reached.',
    });
  }
  if (!response.ok) {
    throw await toApiError(response);
  }
  return response;
};

const toApiError = async (response: Response): Promise<ApiError> => {
  const body: unknown = await response.json().catch(() => null);
  const parsed = apiErrorBodySchema.safeParse(body);
  if (parsed.success) {
    return new ApiError({ ...parsed.data, status: response.status });
  }
  return new ApiError({
    code: CLIENT_ERROR_CODES.unknown,
    status: response.status,
    message: `Request failed with status ${response.status}.`,
  });
};

export const requestJson = async <Schema extends z.ZodType>(
  path: string,
  schema: Schema,
  init?: RequestInit,
): Promise<z.infer<Schema>> => {
  const response = await sendRequest(path, init);
  const parsed = schema.safeParse(await response.json());
  if (!parsed.success) {
    throw new ApiError({
      code: CLIENT_ERROR_CODES.invalidResponse,
      status: response.status,
      message: 'The server sent an unexpected response.',
    });
  }
  return parsed.data;
};

export const requestWithoutContent = async (path: string, init?: RequestInit): Promise<void> => {
  await sendRequest(path, init);
};

export const jsonRequestInit = (method: 'POST' | 'PUT', body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});
