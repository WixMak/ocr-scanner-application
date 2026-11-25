import { ScanSearch } from 'lucide-react';
import { useState, type SubmitEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { ErrorAlert } from '../../components/ErrorAlert';
import { FileDropzone } from '../../components/FileDropzone';
import { PageHeading } from '../../components/PageHeading';
import { useExtractFormValues } from '../../hooks/useExtractFormValues';
import { useTemplateList } from '../../hooks/useTemplateQueries';
import { routeToHash } from '../../routing/routes';
import { ExtractionResultView } from './ExtractionResultView';

const TEMPLATE_SELECT_ID = 'extraction-template';

export const ExtractPage = ({ initialTemplateId }: { initialTemplateId?: string }) => {
  const { t } = useTranslation('extraction');
  const templates = useTemplateList();
  const [templateId, setTemplateId] = useState(initialTemplateId ?? '');
  const [file, setFile] = useState<File | null>(null);
  const extraction = useExtractFormValues();
  const canExtract = templateId !== '' && file !== null && !extraction.isPending;

  const handleSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (file && templateId) {
      extraction.mutate({ templateId, file });
    }
  };

  return (
    <>
      <PageHeading>{t('page.heading')}</PageHeading>
      <p className="page-intro">{t('page.intro')}</p>

      <form className="panel extract-form" onSubmit={handleSubmit}>
        <div className="form-control">
          <label htmlFor={TEMPLATE_SELECT_ID}>{t('page.templateLabel')}</label>
          <select
            id={TEMPLATE_SELECT_ID}
            className="select"
            value={templateId}
            disabled={!templates.data}
            onChange={(event) => setTemplateId(event.target.value)}
          >
            <option value="">{t('page.templatePlaceholder')}</option>
            {templates.data?.map((template) => (
              <option key={template.id} value={template.id}>
                {template.name}
              </option>
            ))}
          </select>
          {templates.data?.length === 0 && (
            <p className="hint">
              {t('page.noTemplates')}{' '}
              <a href={routeToHash({ name: 'newTemplate' })}>{t('page.createTemplate')}</a>
            </p>
          )}
        </div>
        <FileDropzone
          id="filled-form-file"
          label={t('page.fileLabel')}
          selectedFileName={file?.name}
          isDisabled={extraction.isPending}
          onFileSelected={setFile}
        />
        <button type="submit" className="button button--primary extract-form__submit" disabled={!canExtract}>
          <ScanSearch aria-hidden="true" className="icon icon--sm" />
          {extraction.isPending ? t('page.extracting') : t('page.extract')}
        </button>
        <div role="status">
          {extraction.isPending && <p className="loading-text">{t('page.extractingHint')}</p>}
        </div>
      </form>

      {templates.isError && <ErrorAlert error={templates.error} />}
      {extraction.isError && <ErrorAlert error={extraction.error} />}
      {extraction.data && <ExtractionResultView key={extraction.submittedAt} result={extraction.data} />}
    </>
  );
};
