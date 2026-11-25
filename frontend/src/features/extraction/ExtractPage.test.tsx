import { screen, within } from '@testing-library/react';
import {
  RESULT_IMAGE_DATA_URL,
  SECOND_RESULT_IMAGE_DATA_URL,
  TEMPLATE_ID,
  extractionResult,
  makeFile,
  reorderedScanExtractionResult,
  templateSummary,
  twoPageExtractionResult,
} from '../../test/fixtures';
import { mockFetch, neverResolve, respondWith, type RouteHandler } from '../../test/mockFetch';
import { renderWithProviders } from '../../test/renderWithProviders';
import { ExtractPage } from './ExtractPage';

const FILLED_FORM = makeFile('filled.jpg', 'image/jpeg');

const mockExtractionBackend = (extract: RouteHandler = respondWith(extractionResult)) =>
  mockFetch({
    'GET /api/templates': respondWith([templateSummary]),
    'POST /api/extractions': extract,
  });

const renderAndExtract = async (initialTemplateId: string | undefined = TEMPLATE_ID) => {
  const rendered = renderWithProviders(<ExtractPage initialTemplateId={initialTemplateId} />);
  await screen.findByRole('option', { name: 'MPF Enrolment' });
  await rendered.user.upload(screen.getByLabelText('Filled form'), FILLED_FORM);
  await rendered.user.click(screen.getByRole('button', { name: 'Extract values' }));
  return rendered;
};

const readJsonOutput = (): unknown =>
  JSON.parse((screen.getByRole('textbox', { name: 'Extracted values as JSON' }) as HTMLTextAreaElement).value);

describe('ExtractPage', () => {
  it('needs both a template and a file before extracting', async () => {
    mockExtractionBackend();
    const { user } = renderWithProviders(<ExtractPage />);
    const extractButton = screen.getByRole('button', { name: 'Extract values' });

    await screen.findByRole('option', { name: 'MPF Enrolment' });
    expect(extractButton).toBeDisabled();

    await user.selectOptions(screen.getByLabelText('Template'), 'MPF Enrolment');
    expect(extractButton).toBeDisabled();

    await user.upload(screen.getByLabelText('Filled form'), FILLED_FORM);
    expect(extractButton).toBeEnabled();
  });

  it('sends the template and file, then summarises the result', async () => {
    const { calls } = mockExtractionBackend();

    await renderAndExtract();

    expect(
      await screen.findByText('Read 3 fields: 1 confirmed, 1 need review, 1 empty.'),
    ).toBeInTheDocument();
    const extractCall = calls.find((call) => call.path === '/api/extractions');
    const body = extractCall?.body;
    expect(body).toBeInstanceOf(FormData);
    expect(body instanceof FormData && body.get('templateId')).toBe(TEMPLATE_ID);
    expect(screen.getByRole('img', { name: /Filled form lined up with the template/ })).toHaveAttribute(
      'src',
      RESULT_IMAGE_DATA_URL,
    );
  });

  it('shows the ticked option of a choice field as its value', async () => {
    const choiceResult = {
      ...extractionResult,
      values: { bank_account_type: 'Joint 聯名' },
      fields: [
        {
          fieldId: 'field-account-type',
          key: 'bank_account_type',
          label: 'Bank Account Type 銀行帳戶類別',
          fieldType: 'choice',
          pageIndex: 0,
          box: { x: 200, y: 700, width: 434, height: 34 },
          value: 'Joint 聯名',
          confidence: 1,
          status: 'confirmed',
          readings: [],
        },
      ],
    };
    mockExtractionBackend(respondWith(choiceResult));

    await renderAndExtract();

    expect(await screen.findByLabelText('Bank Account Type 銀行帳戶類別')).toHaveValue('Joint 聯名');
    expect(readJsonOutput()).toMatchObject({ values: { bank_account_type: 'Joint 聯名' } });
  });

  it('shows each value with its status, confidence and engine readings', async () => {
    mockExtractionBackend();
    const { user } = await renderAndExtract();

    const phoneInput = await screen.findByRole('textbox', { name: '电话 Phone' });
    expect(phoneInput).toHaveValue('9123 4567');
    expect(phoneInput).toHaveAccessibleDescription('phone Confidence 62%');
    const phoneRow = phoneInput.closest('li');
    if (!phoneRow) {
      throw new Error('Phone row not found');
    }
    expect(within(phoneRow).getByText('Needs review')).toBeInTheDocument();

    await user.click(within(phoneRow).getByText('3 engine readings'));
    expect(within(phoneRow).getByRole('cell', { name: '9123 4561' })).toBeVisible();

    const emptyInput = screen.getByRole('textbox', { name: 'signed_date' });
    expect(emptyInput).toHaveAccessibleDescription('signed_date Confidence —');
  });

  it('jumps from a box on the preview to its value', async () => {
    mockExtractionBackend();
    const { user } = await renderAndExtract();

    await user.click(
      await screen.findByRole('button', { name: '电话 Phone: 9123 4567, Needs review. Go to this value.' }),
    );

    expect(screen.getByRole('textbox', { name: '电话 Phone' })).toHaveFocus();
    expect(
      screen.getByRole('button', { name: 'signed_date: (blank), Empty. Go to this value.' }),
    ).toBeInTheDocument();
  });

  it('updates the JSON and marks the field as edited when a value is corrected', async () => {
    mockExtractionBackend();
    const { user } = await renderAndExtract();

    const phoneInput = await screen.findByRole('textbox', { name: '电话 Phone' });
    await user.clear(phoneInput);
    await user.type(phoneInput, '9123 4568');

    expect(within(phoneInput.closest('li') ?? document.body).getByText('Edited')).toBeInTheDocument();
    expect(readJsonOutput()).toMatchObject({
      templateId: TEMPLATE_ID,
      values: { full_name: '陈大文', phone: '9123 4568', signed_date: '' },
      fields: expect.arrayContaining([expect.objectContaining({ key: 'phone', status: 'edited' })]),
    });
  });

  it('copies the JSON and reports the outcome', async () => {
    mockExtractionBackend();
    const { user } = await renderAndExtract();
    const writeText = jest.spyOn(navigator.clipboard, 'writeText');

    await user.click(await screen.findByRole('button', { name: 'Copy JSON' }));

    expect(await screen.findByText('JSON copied to the clipboard.')).toBeInTheDocument();
    expect(JSON.parse(String(writeText.mock.calls[0]?.[0]))).toEqual(readJsonOutput());

    writeText.mockRejectedValueOnce(new Error('denied'));
    await user.click(screen.getByRole('button', { name: 'Copy JSON' }));
    expect(await screen.findByText(/Couldn't copy automatically/)).toBeInTheDocument();
  });

  it('downloads the JSON as a file', async () => {
    mockExtractionBackend();
    const { user } = await renderAndExtract();
    const createObjectUrl = jest.fn(() => 'blob:extraction');
    const revokeObjectUrl = jest.fn();
    Object.assign(URL, { createObjectURL: createObjectUrl, revokeObjectURL: revokeObjectUrl });
    const click = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);

    await user.click(await screen.findByRole('button', { name: 'Download JSON' }));

    expect(createObjectUrl).toHaveBeenCalledWith(expect.any(Blob));
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:extraction');
  });

  it('warns when the scan could not be aligned to the template', async () => {
    mockExtractionBackend(
      respondWith({
        ...extractionResult,
        pages: [{ ...extractionResult.pages[0], isAligned: false }],
      }),
    );

    await renderAndExtract();

    expect(await screen.findByText(/couldn't be lined up with the template/)).toBeInTheDocument();
  });

  it('shows a multi-page result one page at a time and groups the values by page', async () => {
    mockExtractionBackend(respondWith(twoPageExtractionResult));
    const { user } = await renderAndExtract();
    const pageSwitcher = await screen.findByRole('group', { name: 'Form pages' });
    const signedDateBox = { name: 'signed_date: (blank), Empty. Go to this value.' };

    expect(within(pageSwitcher).getByRole('button', { name: 'Page 1' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('img', { name: /page 1 lined up/ })).toHaveAttribute('src', RESULT_IMAGE_DATA_URL);
    expect(screen.queryByRole('button', signedDateBox)).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: 'Page 2' })).toBeInTheDocument();

    await user.click(within(pageSwitcher).getByRole('button', { name: 'Page 2' }));

    expect(screen.getByRole('img', { name: /page 2 lined up/ })).toHaveAttribute('src', SECOND_RESULT_IMAGE_DATA_URL);
    expect(screen.getByRole('button', signedDateBox)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^姓名 Full Name:/ })).not.toBeInTheDocument();
  });

  it('names the pages that could not be aligned', async () => {
    mockExtractionBackend(respondWith(twoPageExtractionResult));

    await renderAndExtract();

    expect(await screen.findByText(/^Page 2 of the scan couldn't be lined up/)).toBeInTheDocument();
  });

  it('labels a scan without some form pages by the form page numbers', async () => {
    mockExtractionBackend(respondWith(reorderedScanExtractionResult));
    const { user } = await renderAndExtract();
    const pageSwitcher = await screen.findByRole('group', { name: 'Form pages' });
    const pageButtons = within(pageSwitcher).getAllByRole('button');

    expect(pageButtons.map((button) => button.textContent)).toEqual(['Page 1', 'Page 3']);
    expect(screen.getByRole('heading', { level: 3, name: 'Page 3' })).toBeInTheDocument();
    expect(screen.getByText(/^Page 2 of the scan couldn't be lined up/)).toBeInTheDocument();

    await user.click(within(pageSwitcher).getByRole('button', { name: 'Page 3' }));

    expect(screen.getByRole('img', { name: /page 3 lined up/ })).toHaveAttribute('src', SECOND_RESULT_IMAGE_DATA_URL);
    expect(screen.getByRole('button', { name: 'signed_date: (blank), Empty. Go to this value.' })).toBeInTheDocument();
  });

  it('names the form page missing from the scan', async () => {
    mockExtractionBackend(respondWith({ code: 'missing_form_pages', message: 'x', pageNumbers: [2] }, 422));

    await renderAndExtract();

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /^The scan is missing page 2 of the form, which has fields/,
    );
  });

  it('names every form page missing from the scan', async () => {
    mockExtractionBackend(respondWith({ code: 'missing_form_pages', message: 'x', pageNumbers: [2, 4, 5] }, 422));

    await renderAndExtract();

    expect(await screen.findByRole('alert')).toHaveTextContent(/^The scan is missing pages 2, 4, and 5 of the form/);
  });

  it('shows progress while reading and an error when Ollama is down', async () => {
    mockExtractionBackend(neverResolve);
    await renderAndExtract();

    expect(screen.getByText(/Reading handwriting/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Extracting…' })).toBeDisabled();
  });

  it('explains when the OCR engine is unavailable', async () => {
    mockExtractionBackend(respondWith({ code: 'ocr_engine_unavailable', message: 'down' }, 503));

    await renderAndExtract();

    expect(await screen.findByRole('alert')).toHaveTextContent(/OCR model isn't available/);
  });

  it('points to template creation when there are no templates', async () => {
    mockFetch({ 'GET /api/templates': respondWith([]) });

    renderWithProviders(<ExtractPage />);

    expect(await screen.findByRole('link', { name: 'Create one from a blank form.' })).toHaveAttribute(
      'href',
      '#/templates/new',
    );
  });

  it('shows an error when templates cannot be loaded', async () => {
    mockFetch({ 'GET /api/templates': () => ({ status: 500 }) });

    renderWithProviders(<ExtractPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong. Try again.');
  });
});
