import { screen, within } from '@testing-library/react';
import { TEMPLATE_ID, templateSummary } from '../../test/fixtures';
import { mockFetch, neverResolve, respondWith } from '../../test/mockFetch';
import { renderWithProviders } from '../../test/renderWithProviders';
import { TemplateListPage } from './TemplateListPage';

const TEMPLATE_PATH = `/api/templates/${TEMPLATE_ID}`;

describe('TemplateListPage', () => {
  it('shows a loading message while templates load', () => {
    mockFetch({ 'GET /api/templates': neverResolve });

    renderWithProviders(<TemplateListPage />);

    expect(screen.getByRole('status')).toHaveTextContent('Loading templates…');
  });

  it('invites the user to create a first template when there are none', async () => {
    mockFetch({ 'GET /api/templates': respondWith([]) });

    renderWithProviders(<TemplateListPage />);

    expect(await screen.findByText(/No templates yet/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Create a template' })).toHaveAttribute('href', '#/templates/new');
  });

  it('lists templates with edit and extract links', async () => {
    mockFetch({ 'GET /api/templates': respondWith([templateSummary]) });

    renderWithProviders(<TemplateListPage />);

    const row = (await screen.findByRole('rowheader', { name: 'MPF Enrolment' })).closest('tr');
    if (!row) {
      throw new Error('Template row not found');
    }
    expect(within(row).getByRole('cell', { name: '2' })).toBeInTheDocument();
    expect(within(row).getByRole('link', { name: 'Edit MPF Enrolment' })).toHaveAttribute(
      'href',
      `#/templates/${TEMPLATE_ID}`,
    );
    expect(within(row).getByRole('link', { name: 'Extract values with MPF Enrolment' })).toHaveAttribute(
      'href',
      `#/extract/${TEMPLATE_ID}`,
    );
  });

  it('asks for confirmation before deleting and can be cancelled', async () => {
    const { calls } = mockFetch({ 'GET /api/templates': respondWith([templateSummary]) });
    const { user } = renderWithProviders(<TemplateListPage />);

    await user.click(await screen.findByRole('button', { name: 'Delete MPF Enrolment' }));

    expect(screen.getByText('Delete “MPF Enrolment”? This can\'t be undone.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();

    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.getByRole('button', { name: 'Delete MPF Enrolment' })).toBeInTheDocument();
    expect(calls.some((call) => call.method === 'DELETE')).toBe(false);
  });

  it('deletes a template after confirmation and refreshes the list', async () => {
    let templates = [templateSummary];
    const { calls } = mockFetch({
      'GET /api/templates': () => ({ body: templates }),
      [`DELETE ${TEMPLATE_PATH}`]: () => {
        templates = [];
        return { status: 204 };
      },
    });
    const { user } = renderWithProviders(<TemplateListPage />);

    await user.click(await screen.findByRole('button', { name: 'Delete MPF Enrolment' }));
    await user.click(screen.getByRole('button', { name: 'Delete' }));

    expect(await screen.findByText(/No templates yet/)).toBeInTheDocument();
    expect(calls.filter((call) => call.method === 'DELETE')).toHaveLength(1);
  });

  it('shows an error when deleting fails', async () => {
    mockFetch({
      'GET /api/templates': respondWith([templateSummary]),
      [`DELETE ${TEMPLATE_PATH}`]: respondWith({ code: 'template_not_found', message: 'gone' }, 404),
    });
    const { user } = renderWithProviders(<TemplateListPage />);

    await user.click(await screen.findByRole('button', { name: 'Delete MPF Enrolment' }));
    await user.click(screen.getByRole('button', { name: 'Delete' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/doesn't exist anymore/);
  });

  it('explains when the server cannot be reached', async () => {
    globalThis.fetch = jest.fn().mockRejectedValue(new TypeError('Failed to fetch'));

    renderWithProviders(<TemplateListPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent(/server can't be reached/);
  });
});
