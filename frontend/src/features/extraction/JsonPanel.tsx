import { Copy, Download } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { formatFileTimestamp } from '../../utils/formatDateTime';
import type { ExtractionJson } from './extractionView';

const JSON_INDENT = 2;
const JSON_MIME_TYPE = 'application/json';
const JSON_VISIBLE_ROWS = 16;

type CopyOutcome = 'copied' | 'copyFailed' | null;

const downloadJson = (content: string) => {
  const url = URL.createObjectURL(new Blob([content], { type: JSON_MIME_TYPE }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `extraction-${formatFileTimestamp()}.json`;
  link.click();
  URL.revokeObjectURL(url);
};

export const JsonPanel = ({ json }: { json: ExtractionJson }) => {
  const { t } = useTranslation('extraction');
  const [copyOutcome, setCopyOutcome] = useState<CopyOutcome>(null);
  const content = JSON.stringify(json, null, JSON_INDENT);

  const copyJson = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopyOutcome('copied');
    } catch {
      setCopyOutcome('copyFailed');
    }
  };

  return (
    <section className="panel json-panel" aria-labelledby="json-panel-heading">
      <div className="panel__header">
        <h2 id="json-panel-heading" className="panel__title">
          {t('json.heading')}
        </h2>
        <div className="panel__actions">
          <button type="button" className="button button--secondary button--small" onClick={() => void copyJson()}>
            <Copy aria-hidden="true" className="icon icon--sm" />
            {t('json.copy')}
          </button>
          <button type="button" className="button button--secondary button--small" onClick={() => downloadJson(content)}>
            <Download aria-hidden="true" className="icon icon--sm" />
            {t('json.download')}
          </button>
        </div>
      </div>
      <p role="status" className="hint">
        {copyOutcome && t(`json.${copyOutcome}`)}
      </p>
      <textarea
        className="json-panel__code"
        value={content}
        readOnly
        rows={JSON_VISIBLE_ROWS}
        spellCheck={false}
        aria-label={t('json.codeLabel')}
      />
    </section>
  );
};
