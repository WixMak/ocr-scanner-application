import { act, screen, within } from '@testing-library/react';
import i18next from 'i18next';
import { App } from './App';
import { TEMPLATE_ID, healthyStatus, templateSummary } from './test/fixtures';
import { mockFetch, respondWith } from './test/mockFetch';
import { renderWithProviders } from './test/renderWithProviders';

const mockBackend = (health: unknown = healthyStatus) =>
  mockFetch({
    'GET /api/health': respondWith(health),
    'GET /api/templates': respondWith([templateSummary]),
  });

describe('App', () => {
  afterEach(async () => {
    await act(() => i18next.changeLanguage('en'));
  });

  it('shows the template list by default and marks it as the current page', async () => {
    mockBackend();

    renderWithProviders(<App />);

    expect(await screen.findByRole('heading', { level: 1, name: 'Templates' })).toHaveFocus();
    const navigation = screen.getByRole('navigation', { name: 'Main' });
    expect(within(navigation).getByRole('link', { name: 'Templates' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Skip to main content' })).toHaveAttribute('href', '#main-content');
  });

  it('follows hash navigation to the extraction page', async () => {
    mockBackend();
    const { user } = renderWithProviders(<App />);

    await user.click(screen.getByRole('link', { name: 'Extract values' }));

    expect(await screen.findByRole('heading', { level: 1, name: 'Extract values' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Extract values' })).toHaveAttribute('aria-current', 'page');
  });

  it.each([
    ['#/templates/new', 'New template'],
    [`#/templates/${TEMPLATE_ID}`, 'Edit template'],
  ])('opens the template editor for %s', async (hash, heading) => {
    mockBackend();
    window.location.hash = hash;

    renderWithProviders(<App />);

    expect(await screen.findByRole('heading', { level: 1, name: heading })).toBeInTheDocument();
  });

  it('switches the interface to Simplified Chinese and remembers the choice', async () => {
    mockBackend();
    const { user } = renderWithProviders(<App />);

    await user.selectOptions(screen.getByLabelText('Language'), '简体中文');

    expect(await screen.findByRole('heading', { level: 1, name: '模板' })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('zh-CN');
    expect(window.localStorage.getItem('ocr-form-scanner.language')).toBe('zh-CN');
  });

  it('warns when Ollama cannot be reached', async () => {
    mockBackend({ ...healthyStatus, isOllamaReachable: false });

    renderWithProviders(<App />);

    expect(await screen.findByText(/Ollama can't be reached/)).toBeInTheDocument();
  });

  it('names each model that is missing from Ollama', async () => {
    mockBackend({
      ...healthyStatus,
      accurateModel: { model: 'qwen3-vl:8b', isAvailable: false },
    });

    renderWithProviders(<App />);

    expect(await screen.findByText(/ollama pull qwen3-vl:8b/)).toBeInTheDocument();
    expect(screen.queryByText(/qwen3-vl:4b/)).not.toBeInTheDocument();
  });
});
