import { useRef } from 'react';
import { useTranslation } from 'react-i18next';
import type { PageSize, TemplateField } from '../../api/schemas';
import { FormCanvas } from '../../components/FormCanvas';
import { PageSwitcher } from '../../components/PageSwitcher';
import { pageAt } from '../../utils/pages';
import { toImageSize } from './boxGeometry';
import { EditableFieldBox, type BoxCanvas } from './EditableFieldBox';
import { FieldTypeLegend } from './FieldTypeLegend';
import type { FieldEditorActions } from './useFieldEditor';

const BOX_INSTRUCTIONS_ID = 'field-box-instructions';

type TemplatePreviewProps = {
  pages: PageSize[];
  currentPageIndex: number;
  getImageUrl: (pageIndex: number) => string;
  fields: TemplateField[];
  selectedFieldId: string | null;
  actions: FieldEditorActions;
  onPageChange: (pageIndex: number) => void;
};

export const TemplatePreview = ({
  pages,
  currentPageIndex,
  getImageUrl,
  fields,
  selectedFieldId,
  actions,
  onPageChange,
}: TemplatePreviewProps) => {
  const { t } = useTranslation('templates');
  const canvasRef = useRef<HTMLDivElement>(null);
  const imageSize = toImageSize(pageAt(pages, currentPageIndex));
  const fieldsOnPage = fields.filter((field) => field.pageIndex === currentPageIndex);
  const isMultiPage = pages.length > 1;
  const imageAlt = isMultiPage
    ? t('editor.imageAltPage', { number: currentPageIndex + 1, count: pages.length })
    : t('editor.imageAlt');

  const getImagePixelsPerScreenPixel = () => {
    const renderedWidth = canvasRef.current?.getBoundingClientRect().width ?? 0;
    return renderedWidth > 0 ? imageSize.width / renderedWidth : 1;
  };
  const boxCanvas: BoxCanvas = {
    imageSize,
    instructionsId: BOX_INSTRUCTIONS_ID,
    getImagePixelsPerScreenPixel,
  };

  const renderOptionBoxes = (field: TemplateField, fieldName: string) =>
    field.options.map((option, optionIndex) => {
      const optionName = option.label || t('field.optionFallback', { number: optionIndex + 1 });
      return (
        <EditableFieldBox
          key={option.id}
          box={option.box}
          tag={{ text: optionName, fieldType: field.fieldType }}
          accessibleName={t('editor.optionBoxLabel', {
            option: optionName,
            name: fieldName,
            key: field.key,
          })}
          isSelected={field.id === selectedFieldId}
          canvas={boxCanvas}
          onSelect={() => actions.select(field.id)}
          onBoxChange={(box) => actions.setOptionBox(field.id, option.id, box)}
        />
      );
    });

  const renderFieldBoxes = (field: TemplateField) => {
    const fieldName = field.label || field.key;
    if (field.fieldType === 'choice') {
      return renderOptionBoxes(field, fieldName);
    }
    return (
      <EditableFieldBox
        key={field.id}
        box={field.box}
        tag={{ text: field.key, fieldType: field.fieldType }}
        accessibleName={t('editor.boxLabel', {
          name: fieldName,
          key: field.key,
          type: t(`common:fieldTypes.${field.fieldType}`),
        })}
        isSelected={field.id === selectedFieldId}
        canvas={boxCanvas}
        onSelect={() => actions.select(field.id)}
        onBoxChange={(box) => actions.setBox(field.id, box)}
      />
    );
  };

  return (
    <section className="panel editor__preview" aria-labelledby="editor-preview-heading">
      <h2 id="editor-preview-heading" className="panel__title">
        {t('editor.previewHeading')}
      </h2>
      <p id={BOX_INSTRUCTIONS_ID} className="hint">
        {t('editor.boxInstructions')}
      </p>
      <FieldTypeLegend />
      <PageSwitcher
        pageCount={pages.length}
        currentPageIndex={currentPageIndex}
        onPageChange={onPageChange}
      />
      <FormCanvas
        imageUrl={getImageUrl(currentPageIndex)}
        imageSize={imageSize}
        imageAlt={imageAlt}
        canvasRef={canvasRef}
      >
        {fieldsOnPage.map(renderFieldBoxes)}
      </FormCanvas>
    </section>
  );
};
