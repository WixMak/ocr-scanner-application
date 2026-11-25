import { useSyncExternalStore } from 'react';
import { parseRoute, type AppRoute } from './routes';

const subscribeToHashChanges = (onChange: () => void): (() => void) => {
  window.addEventListener('hashchange', onChange);
  return () => window.removeEventListener('hashchange', onChange);
};

const readHash = (): string => window.location.hash;

export const useHashRoute = (): AppRoute => {
  const hash = useSyncExternalStore(subscribeToHashChanges, readHash);
  return parseRoute(hash);
};
