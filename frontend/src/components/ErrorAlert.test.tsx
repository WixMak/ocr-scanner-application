import { screen } from '@testing-library/react';
import { ApiError } from '../api/client';
import { renderWithProviders } from '../test/renderWithProviders';
import { ErrorAlert } from './ErrorAlert';

describe('ErrorAlert', () => {
  it('shows a general message for an unexpected error', () => {
    renderWithProviders(<ErrorAlert error={new TypeError('boom')} />);

    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong. Try again.');
  });

  it('falls back to the general message for an error code it does not know', () => {
    renderWithProviders(<ErrorAlert error={new ApiError({ code: 'teapot', status: 418, message: 'x' })} />);

    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong. Try again.');
  });
});
