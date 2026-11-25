import { fireEvent, screen, within } from '@testing-library/react';
import {
  DRAFT_ID,
  TEMPLATE_ID,
  draft,
  draftWithChoice,
  makeFile,
  template,
  twoPageDraft,
} from '../../test/fixtures';
import { mockFetch, neverResolve, parseJsonBody, respondWith } from '../../test/mockFetch';
import { renderWithProviders } from '../../test/renderWithProviders';
import { KEYBOARD_STEP_PX } from './EditableFieldBox';
import { TemplateEditorPage } from './TemplateEditorPage';

const BLANK_FORM = makeFile('blank.png', 'image/png');
const TEMPLATE_PATH = `/api/templates/${TEMPLATE_ID}`;

const mockNewTemplateBackend = () =>
  mockFetch({
    'POST /api/templates/drafts': respondWith(draft),
    'POST /api/templates': respondWith(template, 201),
    [`PUT ${TEMPLATE_PATH}`]: respondWith(template),
  });

const getFieldRow = (name: string) => screen.getByRole('group', { name });

const uploadBlankForm = async (user: ReturnType<typeof renderWithProviders>['user']) => {
  await user.upload(screen.getByLabelText('Blank form'), BLANK_FORM);
  await screen.findByText(/Detected 2 fields/);
};

describe('TemplateEditorPage — new template', () => {
  it('uploads the blank form and shows the detected fields on the preview', async () => {
    const { calls } = mockNewTemplateBackend();
    const { user } = renderWithProviders(<TemplateEditorPage />);

    expect(screen.getByRole('heading', { level: 1, name: 'New template' })).toHaveFocus();
    await uploadBlankForm(user);

    expect(calls[0]?.body).toBeInstanceOf(FormData);
    expect(screen.getByRole('img', { name: /Blank form with the detected field areas/ })).toHaveAttribute(
      'src',
      `/api/templates/drafts/${DRAFT_ID}/pages/0/image`,
    );
    expect(screen.getByRole('button', { name: 'Field box: 姓名 Full Name (full_name), Text' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '2 fields' })).toBeInTheDocument();
  });

  it('explains the box colours with a legend of every field type', async () => {
    mockNewTemplateBackend();
    const { user } = renderWithProviders(<TemplateEditorPage />);
    await uploadBlankForm(user);

    const legend = screen.getByRole('list', { name: 'Box colours by field type' });

    expect(within(legend).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Text',
      'Number',
      'Date',
      'Choice',
    ]);
  });

  it('shows progress while fields are being detected', async () => {
    mockFetch({ 'POST /api/templates/drafts': neverResolve });
    const { user } = renderWithProviders(<TemplateEditorPage />);

    await user.upload(screen.getByLabelText('Blank form'), BLANK_FORM);

    expect(await screen.findByText(/Detecting fields/)).toBeInTheDocument();
    expect(screen.getByText('Selected: blank.png')).toBeInTheDocument();
  });

  it('rejects unsupported and oversized files before uploading', async () => {
    const { calls } = mockNewTemplateBackend();
    const { user } = renderWithProviders(<TemplateEditorPage />, {
      userEventOptions: { applyAccept: false },
    });
    const input = screen.getByLabelText('Blank form');

    await user.upload(input, makeFile('notes.txt', 'text/plain'));
    expect(screen.getByRole('alert')).toHaveTextContent("This file type isn't supported.");
    expect(input).toHaveAttribute('aria-invalid', 'true');

    await user.upload(input, makeFile('huge.pdf', 'application/pdf', 21 * 1024 * 1024));
    expect(screen.getByRole('alert')).toHaveTextContent('This file is larger than 20 MB.');
    expect(calls).toHaveLength(0);
  });

  it('shows the server error when the form cannot be read', async () => {
    mockFetch({
      'POST /api/templates/drafts': respondWith({ code: 'unsupported_file', message: 'bad' }, 422),
    });
    const { user } = renderWithProviders(<TemplateEditorPage />);

    await user.upload(screen.getByLabelText('Blank form'), BLANK_FORM);

    expect(await screen.findByRole('alert')).toHaveTextContent("couldn't be read as an image or PDF");
  });

  it('blocks saving until the name and keys are valid, then saves and switches to updates', async () => {
    const { calls } = mockNewTemplateBackend();
    const { user } = renderWithProviders(<TemplateEditorPage />);
    await uploadBlankForm(user);

    const keyInput = within(getFieldRow('姓名 Full Name')).getByLabelText('JSON key');
    await user.clear(keyInput);
    await user.type(keyInput, 'Full Name');
    await user.click(screen.getByRole('button', { name: 'Save template' }));

    const summary = screen.getByRole('alert', { name: 'Fix these problems before saving' });
    expect(summary).toHaveFocus();
    expect(within(summary).getByRole('link', { name: 'Enter a template name.' })).toHaveAttribute(
      'href',
      '#template-name',
    );
    expect(keyInput).toHaveAccessibleDescription(/Use lowercase letters, numbers and underscores/);
    expect(calls.filter((call) => call.path === '/api/templates')).toHaveLength(0);

    await user.clear(keyInput);
    await user.type(keyInput, 'full_name');
    await user.type(screen.getByLabelText('Template name'), '  MPF Enrolment ');
    await user.click(screen.getByRole('button', { name: 'Save template' }));

    expect(await screen.findByText(/Template saved at/)).toBeInTheDocument();
    const createCall = calls.find((call) => call.path === '/api/templates');
    expect(parseJsonBody(createCall)).toMatchObject({ name: 'MPF Enrolment', draftId: DRAFT_ID });
    expect(screen.getByRole('link', { name: 'Extract with this template' })).toHaveAttribute(
      'href',
      `#/extract/${TEMPLATE_ID}`,
    );

    await user.click(screen.getByRole('button', { name: 'Save template' }));
    await screen.findByText(/Template saved at/);
    expect(calls.filter((call) => call.method === 'PUT')).toHaveLength(1);
  });

  it('shows a save error from the server', async () => {
    mockFetch({
      'POST /api/templates/drafts': respondWith(draft),
      'POST /api/templates': respondWith({ code: 'field_outside_image', message: 'x' }, 422),
    });
    const { user } = renderWithProviders(<TemplateEditorPage />);
    await uploadBlankForm(user);

    await user.type(screen.getByLabelText('Template name'), 'MPF');
    await user.click(screen.getByRole('button', { name: 'Save template' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('A field box goes outside the form image.');
  });
});

describe('TemplateEditorPage — editing fields', () => {
  it('moves a box with arrow keys and resizes it with Shift + arrow keys', async () => {
    mockNewTemplateBackend();
    const { user } = renderWithProviders(<TemplateEditorPage />);
    await uploadBlankForm(user);
    const box = screen.getByRole('button', { name: 'Field box: 姓名 Full Name (full_name), Text' });
    const row = getFieldRow('姓名 Full Name');

    box.focus();
    await user.keyboard('{ArrowRight}{Shift>}{ArrowDown}{/Shift}{Enter}');

    expect(box).toHaveAttribute('aria-pressed', 'true');
    expect(within(row).getByLabelText('Left')).toHaveValue(384 + KEYBOARD_STEP_PX);
    expect(within(row).getByLabelText('Height')).toHaveValue(75 + KEYBOARD_STEP_PX);
    expect(box).toHaveAccessibleDescription(/use the arrow keys to move it/);
  });

  it('converts drag distance from screen pixels to image pixels', async () => {
    mockNewTemplateBackend();
    const { user } = renderWithProviders(<TemplateEditorPage />);
    await uploadBlankForm(user);
    jest
      .spyOn(HTMLElement.prototype, 'getBoundingClientRect')
      .mockReturnValue({ width: 827 } as DOMRect);
    const box = screen.getByRole('button', { name: 'Field box: 电话 Phone (phone), Number' });

    fireEvent.pointerDown(box, { clientX: 0, clientY: 0, pointerId: 1 });
    fireEvent.pointerMove(box, { clientX: 10, clientY: 5, pointerId: 1 });
    fireEvent.pointerUp(box, { pointerId: 1 });

    expect(within(getFieldRow('电话 Phone')).getByLabelText('Left')).toHaveValue(348);
    expect(within(getFieldRow('电话 Phone')).getByLabelText('Top')).toHaveValue(492);
  });

  it('moves and resizes a box by dragging', async () => {
    mockNewTemplateBackend();
    const { user } = renderWithProviders(<TemplateEditorPage />);
    await uploadBlankForm(user);
    const box = screen.getByRole('button', { name: 'Field box: 电话 Phone (phone), Number' });
    const row = getFieldRow('电话 Phone');

    fireEvent.pointerDown(box, { clientX: 100, clientY: 100, pointerId: 1 });
    fireEvent.pointerMove(box, { clientX: 130, clientY: 80, pointerId: 1 });
    fireEvent.pointerUp(box, { pointerId: 1 });
    fireEvent.pointerMove(box, { clientX: 500, clientY: 500, pointerId: 1 });

    expect(within(row).getByLabelText('Left')).toHaveValue(358);
    expect(within(row).getByLabelText('Top')).toHaveValue(462);

    const handle = box.querySelector('.field-box__resize-handle');
    if (!handle) {
      throw new Error('Resize handle not found');
    }
    fireEvent.pointerDown(handle, { clientX: 0, clientY: 0, pointerId: 2 });
    fireEvent.pointerMove(handle, { clientX: -100, clientY: 14, pointerId: 2 });
    fireEvent.pointerCancel(handle, { pointerId: 2 });

    expect(within(row).getByLabelText('Width')).toHaveValue(1103);
    expect(within(row).getByLabelText('Height')).toHaveValue(100);
  });

  it('edits label, type and exact position from the field panel', async () => {
    mockNewTemplateBackend();
    const { user } = renderWithProviders(<TemplateEditorPage />);
    await uploadBlankForm(user);
    const row = getFieldRow('电话 Phone');

    await user.selectOptions(within(row).getByLabelText('Type'), 'Date');
    const leftInput = within(row).getByLabelText('Left');
    await user.clear(leftInput);
    await user.type(leftInput, '400');
    await user.clear(within(row).getByLabelText('Label'));
    await user.type(within(row).getByLabelText('Label'), 'Mobile');

    const renamedRow = getFieldRow('Mobile');
    expect(within(renamedRow).getByLabelText('Type')).toHaveValue('date');
    expect(within(renamedRow).getByLabelText('Left')).toHaveValue(400);
    expect(renamedRow.closest('li')).toHaveClass('field-row--selected');
    expect(screen.getByRole('button', { name: 'Field box: Mobile (phone), Date' })).toBeInTheDocument();
  });

  it('turns a field into a choice whose options can be added, renamed and removed', async () => {
    mockNewTemplateBackend();
    const { user } = renderWithProviders(<TemplateEditorPage />);
    await uploadBlankForm(user);
    const row = getFieldRow('电话 Phone');

    await user.selectOptions(within(row).getByLabelText('Type'), 'Choice');

    const options = within(row).getByRole('group', { name: 'Options' });
    expect(options).toHaveAccessibleDescription('The extracted value is the text of the ticked option.');
    expect(within(options).getByLabelText('Option text')).toHaveValue('电话 Phone');
    expect(within(options).queryByRole('button', { name: /Remove option/ })).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Option box: 电话 Phone for 电话 Phone (phone)' }),
    ).toBeInTheDocument();

    await user.click(within(options).getByRole('button', { name: 'Add option' }));
    const newOption = within(options).getByRole('group', { name: 'Option 2' });
    expect(within(newOption).getByLabelText('Option text')).toHaveFocus();
    await user.type(within(newOption).getByLabelText('Option text'), 'Fax');
    expect(
      screen.getByRole('button', { name: 'Option box: Fax for 电话 Phone (phone)' }),
    ).toBeInTheDocument();

    await user.click(within(options).getByRole('button', { name: 'Remove option Fax' }));
    expect(within(options).getByRole('button', { name: 'Add option' })).toHaveFocus();
    expect(screen.queryByRole('button', { name: /Option box: Fax/ })).not.toBeInTheDocument();

    await user.selectOptions(within(row).getByLabelText('Type'), 'Text');
    expect(within(row).queryByRole('group', { name: 'Options' })).not.toBeInTheDocument();
    expect(within(row).getByLabelText('Left')).toHaveValue(328);
  });

  it('moves a detected option box and saves the choice with its options', async () => {
    const { calls } = mockFetch({
      'POST /api/templates/drafts': respondWith(draftWithChoice),
      'POST /api/templates': respondWith(template, 201),
    });
    const { user } = renderWithProviders(<TemplateEditorPage />);
    await uploadBlankForm(user);
    const jointBox = screen.getByRole('button', {
      name: 'Option box: Joint 聯名 for Bank Account Type 銀行帳戶類別 (bank_account_type)',
    });

    jointBox.focus();
    await user.keyboard('{ArrowDown}');
    const jointOption = within(getFieldRow('Bank Account Type 銀行帳戶類別')).getByRole('group', {
      name: 'Joint 聯名',
    });
    const leftInput = within(jointOption).getByLabelText('Left');
    await user.clear(leftInput);
    await user.type(leftInput, '650');
    await user.type(screen.getByLabelText('Template name'), 'Direct debit');
    await user.click(screen.getByRole('button', { name: 'Save template' }));

    await screen.findByText(/Template saved at/);
    const createCall = calls.find((call) => call.path === '/api/templates');
    expect(parseJsonBody(createCall)).toMatchObject({
      fields: [
        { key: 'full_name' },
        {
          key: 'bank_account_type',
          fieldType: 'choice',
          box: { x: 200, y: 700, width: 484, height: 39 },
          options: [
            { label: 'Personal 個人', box: { x: 200, y: 700, width: 34, height: 34 } },
            { label: 'Joint 聯名', box: { x: 650, y: 705, width: 34, height: 34 } },
          ],
        },
      ],
    });
  });

  it('adds a field and focuses its key, then removes it and returns focus to the list', async () => {
    mockNewTemplateBackend();
    const { user } = renderWithProviders(<TemplateEditorPage />);
    await uploadBlankForm(user);

    await user.click(screen.getByRole('button', { name: 'Add field' }));

    const newRow = getFieldRow('field_3');
    expect(within(newRow).getByLabelText('JSON key')).toHaveFocus();
    expect(screen.getByRole('heading', { name: '3 fields' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Field box: field_3 (field_3), Text' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );

    await user.clear(within(newRow).getByLabelText('JSON key'));
    await user.click(screen.getByRole('button', { name: 'Save template' }));
    expect(
      screen.getByRole('link', { name: 'Unnamed field: enter a JSON key.' }),
    ).toBeInTheDocument();
    await user.type(within(newRow).getByLabelText('JSON key'), 'field_3');

    await user.click(within(newRow).getByRole('button', { name: 'Remove field_3' }));
    await user.click(within(getFieldRow('电话 Phone')).getByRole('button', { name: 'Remove 电话 Phone' }));
    await user.click(within(getFieldRow('姓名 Full Name')).getByRole('button', { name: 'Remove 姓名 Full Name' }));

    expect(screen.getByRole('heading', { name: '0 fields' })).toHaveFocus();
    expect(screen.getByText(/No fields yet/)).toBeInTheDocument();
  });
});

describe('TemplateEditorPage — multi-page form', () => {
  const mockTwoPageBackend = () =>
    mockFetch({
      'POST /api/templates/drafts': respondWith(twoPageDraft),
      'POST /api/templates': respondWith(template, 201),
    });

  const uploadTwoPageForm = async (user: ReturnType<typeof renderWithProviders>['user']) => {
    await user.upload(screen.getByLabelText('Blank form'), BLANK_FORM);
    await screen.findByText(/Detected 3 fields/);
  };

  it('shows one page at a time and groups the fields by page', async () => {
    mockTwoPageBackend();
    const { user } = renderWithProviders(<TemplateEditorPage />);
    await uploadTwoPageForm(user);
    const pageSwitcher = screen.getByRole('group', { name: 'Form pages' });

    expect(within(pageSwitcher).getByRole('button', { name: 'Page 1' })).toHaveAttribute('aria-pressed', 'true');
    expect(
      screen.getByRole('img', { name: 'Blank form page 1 of 2 with the detected field areas outlined' }),
    ).toHaveAttribute('src', `/api/templates/drafts/${DRAFT_ID}/pages/0/image`);
    expect(screen.queryByRole('button', { name: 'Field box: Signature (signature), Text' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: 'Page 2' })).toBeInTheDocument();

    await user.click(within(pageSwitcher).getByRole('button', { name: 'Page 2' }));

    expect(within(pageSwitcher).getByRole('button', { name: 'Page 2' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('img', { name: /page 2 of 2/ })).toHaveAttribute(
      'src',
      `/api/templates/drafts/${DRAFT_ID}/pages/1/image`,
    );
    expect(screen.getByRole('button', { name: 'Field box: Signature (signature), Text' })).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Field box: 姓名 Full Name (full_name), Text' }),
    ).not.toBeInTheDocument();
  });

  it('jumps to the page of a field chosen in the list', async () => {
    mockTwoPageBackend();
    const { user } = renderWithProviders(<TemplateEditorPage />);
    await uploadTwoPageForm(user);

    await user.click(within(getFieldRow('Signature')).getByLabelText('Label'));

    expect(screen.getByRole('img', { name: /page 2 of 2/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Field box: Signature (signature), Text' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('adds a new field to the page being shown and saves its page', async () => {
    const { calls } = mockTwoPageBackend();
    const { user } = renderWithProviders(<TemplateEditorPage />);
    await uploadTwoPageForm(user);

    await user.click(screen.getByRole('button', { name: 'Page 2' }));
    await user.click(screen.getByRole('button', { name: 'Add field' }));
    await user.type(screen.getByLabelText('Template name'), 'DDA');
    await user.click(screen.getByRole('button', { name: 'Save template' }));

    await screen.findByText(/Template saved at/);
    const createCall = calls.find((call) => call.path === '/api/templates');
    expect(parseJsonBody(createCall)).toMatchObject({
      fields: [{ pageIndex: 0 }, { pageIndex: 0 }, { pageIndex: 1 }, { key: 'field_4', pageIndex: 1 }],
    });
  });
});

describe('TemplateEditorPage — existing template', () => {
  it('loads the saved template and updates it', async () => {
    const { calls } = mockFetch({
      [`GET ${TEMPLATE_PATH}`]: respondWith(template),
      [`PUT ${TEMPLATE_PATH}`]: respondWith({ ...template, name: 'Renamed' }),
    });
    const { user } = renderWithProviders(<TemplateEditorPage templateId={TEMPLATE_ID} />);

    expect(screen.getByRole('status')).toHaveTextContent('Loading template…');
    const nameInput = await screen.findByLabelText('Template name');
    expect(nameInput).toHaveValue('MPF Enrolment');
    expect(screen.getByRole('img')).toHaveAttribute('src', `${TEMPLATE_PATH}/pages/0/image`);

    await user.clear(nameInput);
    await user.type(nameInput, 'Renamed');
    await user.click(screen.getByRole('button', { name: 'Save template' }));

    await screen.findByText(/Template saved at/);
    expect(parseJsonBody(calls.find((call) => call.method === 'PUT'))).toMatchObject({ name: 'Renamed' });
  });

  it('shows an error when the template does not exist', async () => {
    mockFetch({
      [`GET ${TEMPLATE_PATH}`]: respondWith({ code: 'template_not_found', message: 'x' }, 404),
    });

    renderWithProviders(<TemplateEditorPage templateId={TEMPLATE_ID} />);

    expect(await screen.findByRole('alert')).toHaveTextContent(/doesn't exist anymore/);
    expect(screen.getByRole('link', { name: 'Back to templates' })).toHaveAttribute('href', '#/templates');
  });
});
