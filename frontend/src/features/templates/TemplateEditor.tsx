import { CircleCheck } from 'lucide-react';
import { useState, type SubmitEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { getDraftImageUrl, getTemplateImageUrl } from '../../api/formScannerApi';
import type { PageSize, Template, TemplateDraft, TemplateField } from '../../api/schemas';
import { ErrorAlert } from '../../components/ErrorAlert';
import { useSaveTemplate, type SaveTemplateTarget } from '../../hooks/useTemplateQueries';
import { formatTime } from '../../utils/formatDateTime';
import { pageAt } from '../../utils/pages';
import { toImageSize } from './boxGeometry';
import { FieldEditorPanel } from './FieldEditorPanel';
import { TemplateEditorToolbar, TEMPLATE_NAME_INPUT_ID } from './TemplateEditorToolbar';
import { TemplateErrorSummary } from './TemplateErrorSummary';
import { TemplatePreview } from './TemplatePreview';
import { isTemplateValid, validateTemplate } from './templateValidation';
import { useFieldEditor } from './useFieldEditor';

export type EditorSource =
  | { kind: 'draft'; draft: TemplateDraft }
  | { kind: 'saved'; template: Template };

type EditorStartingPoint = {
  getImageUrl: (pageIndex: number) => string;
  pages: PageSize[];
  name: string;
  fields: TemplateField[];
  target: SaveTemplateTarget;
};

const NO_KEY_PROBLEMS = new Map<string, never>();

const describeSource = (source: EditorSource): EditorStartingPoint => {
  if (source.kind === 'draft') {
    const { draft } = source;
    return {
      getImageUrl: (pageIndex) => getDraftImageUrl(draft.draftId, pageIndex),
      pages: draft.pages,
      name: '',
      fields: draft.fields,
      target: { kind: 'draft', draftId: draft.draftId },
    };
  }
  const { template } = source;
  return {
    getImageUrl: (pageIndex) => getTemplateImageUrl(template.id, pageIndex),
    pages: template.pages,
    name: template.name,
    fields: template.fields,
    target: { kind: 'saved', templateId: template.id },
  };
};

export const TemplateEditor = ({ source }: { source: EditorSource }) => {
  const { t } = useTranslation('templates');
  const [startingPoint] = useState(() => describeSource(source));
  const { pages } = startingPoint;
  const [name, setName] = useState(startingPoint.name);
  const [target, setTarget] = useState(startingPoint.target);
  const [hasTriedSaving, setHasTriedSaving] = useState(false);
  const [failedSaveAttempts, setFailedSaveAttempts] = useState(0);
  const editor = useFieldEditor(startingPoint.fields);
  const saveTemplate = useSaveTemplate();

  const validation = validateTemplate(name, editor.fields);
  const shouldShowProblems = hasTriedSaving && !isTemplateValid(validation);

  const handleSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    setHasTriedSaving(true);
    if (!isTemplateValid(validation)) {
      setFailedSaveAttempts((attempts) => attempts + 1);
      return;
    }
    saveTemplate.mutate(
      { target, input: { name: name.trim(), fields: editor.fields } },
      { onSuccess: (template) => setTarget({ kind: 'saved', templateId: template.id }) },
    );
  };

  return (
    <form className="editor" onSubmit={handleSubmit} noValidate>
      <TemplateEditorToolbar
        name={name}
        isNameInvalid={hasTriedSaving && validation.isNameMissing}
        isSaving={saveTemplate.isPending}
        savedTemplateId={target.kind === 'saved' ? target.templateId : null}
        onNameChange={setName}
        onAddField={() => editor.addField(toImageSize(pageAt(pages, editor.currentPageIndex)))}
      />
      <div role="status" className="editor__status">
        {saveTemplate.data && (
          <p className="inline-status inline-status--success">
            <CircleCheck aria-hidden="true" className="icon icon--sm" />
            {t('editor.saved', { time: formatTime(saveTemplate.data.updatedAt) })}
          </p>
        )}
      </div>
      {shouldShowProblems && (
        <TemplateErrorSummary
          key={failedSaveAttempts}
          validation={validation}
          fields={editor.fields}
          nameInputId={TEMPLATE_NAME_INPUT_ID}
        />
      )}
      {saveTemplate.isError && <ErrorAlert error={saveTemplate.error} />}

      <div className="editor__body">
        <TemplatePreview
          pages={pages}
          currentPageIndex={editor.currentPageIndex}
          getImageUrl={startingPoint.getImageUrl}
          fields={editor.fields}
          selectedFieldId={editor.selectedFieldId}
          actions={editor.actions}
          onPageChange={editor.showPage}
        />
        <FieldEditorPanel
          fields={editor.fields}
          keyProblems={hasTriedSaving ? validation.keyProblems : NO_KEY_PROBLEMS}
          selectedFieldId={editor.selectedFieldId}
          addedFieldId={editor.addedFieldId}
          pages={pages}
          actions={editor.actions}
        />
      </div>
    </form>
  );
};
