export type AppRoute =
  | { name: 'templates' }
  | { name: 'newTemplate' }
  | { name: 'editTemplate'; templateId: string }
  | { name: 'extract'; templateId?: string };

const TEMPLATES_SEGMENT = 'templates';
const NEW_SEGMENT = 'new';
const EXTRACT_SEGMENT = 'extract';

export const DEFAULT_ROUTE: AppRoute = { name: 'templates' };

export const parseRoute = (hash: string): AppRoute => {
  const [section, detail] = hash
    .replace(/^#\/?/, '')
    .split('/')
    .filter(Boolean)
    .map(decodeURIComponent);

  if (section === EXTRACT_SEGMENT) {
    return detail ? { name: 'extract', templateId: detail } : { name: 'extract' };
  }
  if (section === TEMPLATES_SEGMENT && detail === NEW_SEGMENT) {
    return { name: 'newTemplate' };
  }
  if (section === TEMPLATES_SEGMENT && detail) {
    return { name: 'editTemplate', templateId: detail };
  }
  return DEFAULT_ROUTE;
};

export const routeToHash = (route: AppRoute): string => {
  switch (route.name) {
    case 'templates':
      return `#/${TEMPLATES_SEGMENT}`;
    case 'newTemplate':
      return `#/${TEMPLATES_SEGMENT}/${NEW_SEGMENT}`;
    case 'editTemplate':
      return `#/${TEMPLATES_SEGMENT}/${encodeURIComponent(route.templateId)}`;
    case 'extract':
      return route.templateId
        ? `#/${EXTRACT_SEGMENT}/${encodeURIComponent(route.templateId)}`
        : `#/${EXTRACT_SEGMENT}`;
  }
};
