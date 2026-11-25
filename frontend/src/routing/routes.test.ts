import { parseRoute, routeToHash, type AppRoute } from './routes';

describe('routes', () => {
  it.each<[string, AppRoute]>([
    ['', { name: 'templates' }],
    ['#/templates', { name: 'templates' }],
    ['#/templates/new', { name: 'newTemplate' }],
    ['#/templates/abc123', { name: 'editTemplate', templateId: 'abc123' }],
    ['#/extract', { name: 'extract' }],
    ['#/extract/abc123', { name: 'extract', templateId: 'abc123' }],
    ['#/unknown/page', { name: 'templates' }],
  ])('parses %s', (hash, expected) => {
    expect(parseRoute(hash)).toEqual(expected);
  });

  it.each<AppRoute>([
    { name: 'templates' },
    { name: 'newTemplate' },
    { name: 'editTemplate', templateId: 'id with/slash' },
    { name: 'extract' },
    { name: 'extract', templateId: 'abc' },
  ])('round-trips %o through the hash', (route) => {
    expect(parseRoute(routeToHash(route))).toEqual(route);
  });
});
