import { TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ExtractionResult, ResultPage } from '../../api/schemas';
import { FormCanvas } from '../../components/FormCanvas';
import { PageSwitcher } from '../../components/PageSwitcher';
import { groupByPage, pageAt } from '../../utils/pages';
import { toImageSize } from '../templates/boxGeometry';
import { ExtractedFieldRow } from './ExtractedFieldRow';
import {
  buildExtractionJson,
  countByStatus,
  toFieldViews,
  type EditedValues,
  type ExtractedFieldView,
} from './extractionView';
import { JsonPanel } from './JsonPanel';
import { ResultFieldBox } from './ResultFieldBox';

const AlignmentWarning = ({ pages }: { pages: ResultPage[] }) => {
  const { t, i18n } = useTranslation('extraction');
  const unalignedPageNumbers = pages
    .filter((page) => !page.isAligned)
    .map((page) => String(page.scanPageNumber));
  if (unalignedPageNumbers.length === 0) {
    return null;
  }
  const listFormatter = new Intl.ListFormat(i18n.language, { type: 'conjunction' });
  const message =
    pages.length > 1
      ? t('result.notAlignedPages', {
          count: unalignedPageNumbers.length,
          pages: listFormatter.format(unalignedPageNumbers),
        })
      : t('result.notAligned');

  return (
    <div className="banner banner--warning">
      <TriangleAlert aria-hidden="true" className="icon icon--md banner__icon" />
      <p>{message}</p>
    </div>
  );
};

export const ExtractionResultView = ({ result }: { result: ExtractionResult }) => {
  const { t, i18n } = useTranslation('extraction');
  const [editedValues, setEditedValues] = useState<EditedValues>({});
  const [currentPageIndex, setCurrentPageIndex] = useState(0);
  const fieldViews = toFieldViews(result, editedValues);
  const statusCounts = countByStatus(result.fields);
  const currentPage = pageAt(result.pages, currentPageIndex);
  const imageSize = toImageSize(currentPage);
  const isMultiPage = result.pages.length > 1;
  const percentFormatter = new Intl.NumberFormat(i18n.language, { style: 'percent' });
  const templatePageCount = Math.max(...result.pages.map((page) => page.pageIndex)) + 1;
  const imageAlt = isMultiPage
    ? t('result.imageAltPage', { number: currentPage.pageIndex + 1 })
    : t('result.imageAlt');

  const updateValue = (fieldId: string, value: string) =>
    setEditedValues((current) => ({ ...current, [fieldId]: value }));

  const renderRows = (rowFields: ExtractedFieldView[]) => (
    <ul className="extracted-list">
      {rowFields.map((field) => (
        <ExtractedFieldRow
          key={field.fieldId}
          field={field}
          formatConfidence={(confidence) => percentFormatter.format(confidence)}
          onValueChange={updateValue}
        />
      ))}
    </ul>
  );

  const renderPageGroups = () =>
    groupByPage(fieldViews, templatePageCount).map((group) => (
      <section
        key={group.pageIndex}
        className="field-group"
        aria-labelledby={`result-group-${group.pageIndex}`}
      >
        <h3 id={`result-group-${group.pageIndex}`} className="field-group__heading">
          {t('common:pages.page', { number: group.pageIndex + 1 })}
        </h3>
        {renderRows(group.items)}
      </section>
    ));

  return (
    <div className="result">
      <p role="status" className="result__summary">
        {t('result.summary', {
          total: result.fields.length,
          confirmed: statusCounts.confirmed,
          review: statusCounts.review,
          empty: statusCounts.empty,
        })}
      </p>
      <AlignmentWarning pages={result.pages} />
      <div className="result__body">
        <section className="panel result__preview" aria-labelledby="result-preview-heading">
          <h2 id="result-preview-heading" className="panel__title">
            {t('result.previewHeading')}
          </h2>
          <PageSwitcher
            pageCount={result.pages.length}
            currentPageIndex={currentPageIndex}
            onPageChange={setCurrentPageIndex}
            getPageNumber={(pageIndex) => pageAt(result.pages, pageIndex).pageIndex + 1}
          />
          <FormCanvas imageUrl={currentPage.imageDataUrl} imageSize={imageSize} imageAlt={imageAlt}>
            {fieldViews
              .filter((field) => field.pageIndex === currentPage.pageIndex)
              .map((field) => (
                <ResultFieldBox key={field.fieldId} field={field} imageSize={imageSize} />
              ))}
          </FormCanvas>
        </section>
        <section className="panel result__fields" aria-labelledby="result-fields-heading">
          <h2 id="result-fields-heading" className="panel__title">
            {t('result.fieldsHeading')}
          </h2>
          {isMultiPage ? renderPageGroups() : renderRows(fieldViews)}
        </section>
      </div>
      <JsonPanel json={buildExtractionJson(result, fieldViews)} />
    </div>
  );
};
