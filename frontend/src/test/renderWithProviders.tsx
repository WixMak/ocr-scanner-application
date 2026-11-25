import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactElement } from 'react';

type RenderOptions = { userEventOptions?: Parameters<typeof userEvent.setup>[0] };

export const renderWithProviders = (ui: ReactElement, { userEventOptions }: RenderOptions = {}) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    user: userEvent.setup(userEventOptions),
    ...render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>),
  };
};
