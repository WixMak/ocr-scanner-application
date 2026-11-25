import { ArrowLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { ErrorAlert } from '../../components/ErrorAlert';
import { FileDropzone } from '../../components/FileDropzone';
import { PageHeading } from '../../components/PageHeading';
import { useCreateTemplateDraft, useTemplate } from '../../hooks/useTemplateQueries';
import { routeToHash } from '../../routing/routes';
import { TemplateEditor } from './TemplateEditor';

const BackToTemplatesLink = () => {
  const { t } = useTranslation('templates');
  return (
    <a className="back-link" href={routeToHash({ name: 'templates' })}>
      <ArrowLeft aria-hidden="true" className="icon icon--sm" />
      {t('editor.backToTemplates')}
    </a>
  );
};

const NewTemplateEditor = () => {
  const { t } = useTranslation('templates');
  const createDraft = useCreateTemplateDraft();

  if (createDraft.data) {
    return (
      <>
        <p role="status" className="inline-status">
          {t('new.detectedFields', { count: createDraft.data.fields.length })}
        </p>
        <TemplateEditor key={createDraft.data.draftId} source={{ kind: 'draft', draft: createDraft.data }} />
      </>
    );
  }

  return (
    <section className="panel upload-panel" aria-labelledby="new-template-upload-heading">
      <h2 id="new-template-upload-heading" className="panel__title">
        {t('new.uploadHeading')}
      </h2>
      <p className="page-intro">{t('new.uploadIntro')}</p>
      <FileDropzone
        id="blank-form-file"
        label={t('new.fileLabel')}
        isDisabled={createDraft.isPending}
        selectedFileName={createDraft.variables?.name}
        onFileSelected={(file) => createDraft.mutate(file)}
      />
      <div role="status">
        {createDraft.isPending && <p className="loading-text">{t('new.detecting')}</p>}
      </div>
      {createDraft.isError && <ErrorAlert error={createDraft.error} />}
    </section>
  );
};

const SavedTemplateEditor = ({ templateId }: { templateId: string }) => {
  const { t } = useTranslation('templates');
  const template = useTemplate(templateId);

  if (template.isPending) {
    return (
      <p role="status" className="loading-text">
        {t('edit.loading')}
      </p>
    );
  }
  if (template.isError) {
    return <ErrorAlert error={template.error} />;
  }
  return <TemplateEditor key={template.data.id} source={{ kind: 'saved', template: template.data }} />;
};

export const TemplateEditorPage = ({ templateId }: { templateId?: string }) => {
  const { t } = useTranslation('templates');

  return (
    <>
      <BackToTemplatesLink />
      <PageHeading>{templateId ? t('edit.heading') : t('new.heading')}</PageHeading>
      {templateId ? <SavedTemplateEditor templateId={templateId} /> : <NewTemplateEditor />}
    </>
  );
};
