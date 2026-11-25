type MockResponseInit = { status?: number; body?: unknown };

export type FetchCall = { method: string; path: string; body: RequestInit['body'] };

export type RouteHandler = (call: FetchCall) => MockResponseInit | Promise<MockResponseInit>;

const OK_STATUS = 200;
const NOT_FOUND_STATUS = 404;
const SUCCESS_STATUS_LIMIT = 300;

const toResponse = ({ status = OK_STATUS, body }: MockResponseInit): Response =>
  ({
    ok: status < SUCCESS_STATUS_LIMIT,
    status,
    json: () => (body === undefined ? Promise.reject(new SyntaxError('No body')) : Promise.resolve(body)),
  }) as Response;

/**
 * Mocks the network boundary. Routes are keyed by "METHOD /api/path".
 * Returns every call so tests can assert on what was sent.
 */
export const mockFetch = (routes: Record<string, RouteHandler>) => {
  const calls: FetchCall[] = [];
  const fetchMock = jest.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const call = { method: init?.method ?? 'GET', path: String(input), body: init?.body };
    calls.push(call);
    const handler = routes[`${call.method} ${call.path}`];
    if (!handler) {
      return toResponse({ status: NOT_FOUND_STATUS, body: { code: 'not_mocked', message: call.path } });
    }
    return toResponse(await handler(call));
  });
  globalThis.fetch = fetchMock;
  return { calls, fetchMock };
};

export const respondWith =
  (body: unknown, status = OK_STATUS): RouteHandler =>
  () => ({ body, status });

export const neverResolve: RouteHandler = () => new Promise(() => undefined);

export const parseJsonBody = (call: FetchCall | undefined): unknown =>
  typeof call?.body === 'string' ? JSON.parse(call.body) : undefined;
