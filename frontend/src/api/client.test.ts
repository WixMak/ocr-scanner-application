import { z } from 'zod';
import { mockFetch, respondWith } from '../test/mockFetch';
import { ApiError, CLIENT_ERROR_CODES, requestJson, requestWithoutContent } from './client';

const greetingSchema = z.object({ greeting: z.string() });

const captureError = async (promise: Promise<unknown>): Promise<ApiError> => {
  try {
    await promise;
  } catch (error) {
    if (error instanceof ApiError) {
      return error;
    }
  }
  throw new Error('Expected the request to fail with an ApiError');
};

describe('requestJson', () => {
  it('returns the validated response body', async () => {
    mockFetch({ 'GET /api/hello': respondWith({ greeting: '你好' }) });

    await expect(requestJson('/hello', greetingSchema)).resolves.toEqual({ greeting: '你好' });
  });

  it('rejects responses that do not match the schema', async () => {
    mockFetch({ 'GET /api/hello': respondWith({ greeting: 42 }) });

    const error = await captureError(requestJson('/hello', greetingSchema));

    expect(error.code).toBe(CLIENT_ERROR_CODES.invalidResponse);
  });

  it('uses the server error code when the backend explains the failure', async () => {
    mockFetch({
      'GET /api/hello': respondWith({ code: 'template_not_found', message: 'Template not found.' }, 404),
    });

    const error = await captureError(requestJson('/hello', greetingSchema));

    expect(error).toMatchObject({ code: 'template_not_found', status: 404, pageNumbers: [] });
  });

  it('keeps the page numbers the backend names in an error', async () => {
    mockFetch({
      'POST /api/hello': respondWith({ code: 'missing_form_pages', message: 'Missing.', pageNumbers: [2, 4] }, 422),
    });

    const error = await captureError(requestWithoutContent('/hello', { method: 'POST' }));

    expect(error).toMatchObject({ code: 'missing_form_pages', status: 422, pageNumbers: [2, 4] });
  });

  it('falls back to an unknown error for unexplained failures', async () => {
    mockFetch({ 'DELETE /api/hello': () => ({ status: 500 }) });

    const error = await captureError(requestWithoutContent('/hello', { method: 'DELETE' }));

    expect(error).toMatchObject({ code: CLIENT_ERROR_CODES.unknown, status: 500 });
  });

  it('reports a network error when the server cannot be reached', async () => {
    globalThis.fetch = jest.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    const error = await captureError(requestJson('/hello', greetingSchema));

    expect(error).toMatchObject({ code: CLIENT_ERROR_CODES.network, status: 0 });
  });
});
