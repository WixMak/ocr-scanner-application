import { FileUp } from 'lucide-react';
import { useState, type ChangeEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { MAX_UPLOAD_BYTES } from '../api/client';

export const ACCEPTED_FILE_TYPES = [
  'image/png',
  'image/jpeg',
  'image/tiff',
  'image/webp',
  'application/pdf',
] as const;

const BYTES_PER_MEGABYTE = 1024 * 1024;
const MAX_UPLOAD_MEGABYTES = MAX_UPLOAD_BYTES / BYTES_PER_MEGABYTE;

type FileProblem = 'tooLarge' | 'unsupportedType';

const findFileProblem = (file: File): FileProblem | null => {
  if (!ACCEPTED_FILE_TYPES.some((type) => type === file.type)) {
    return 'unsupportedType';
  }
  return file.size > MAX_UPLOAD_BYTES ? 'tooLarge' : null;
};

type FileDropzoneProps = {
  id: string;
  label: string;
  selectedFileName?: string;
  isDisabled?: boolean;
  onFileSelected: (file: File) => void;
};

export const FileDropzone = ({
  id,
  label,
  selectedFileName,
  isDisabled = false,
  onFileSelected,
}: FileDropzoneProps) => {
  const { t } = useTranslation();
  const [problem, setProblem] = useState<FileProblem | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const hintId = `${id}-hint`;
  const problemId = `${id}-problem`;

  const acceptFile = (file: File | undefined) => {
    if (!file) {
      return;
    }
    const fileProblem = findFileProblem(file);
    setProblem(fileProblem);
    if (!fileProblem) {
      onFileSelected(file);
    }
  };

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    acceptFile(event.target.files?.[0]);
    event.target.value = '';
  };

  const dropzoneClassName = [
    'dropzone',
    isDragActive ? 'dropzone--active' : '',
    isDisabled ? 'dropzone--disabled' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className="dropzone-field">
      <p className="field-label" id={`${id}-label`}>
        {label}
      </p>
      <label className={dropzoneClassName}>
        <FileUp aria-hidden="true" className="icon icon--lg dropzone__icon" />
        <span className="dropzone__action">{t('upload.chooseFile')}</span>
        <span className="dropzone__secondary">{t('upload.dropHint')}</span>
        {/* The transparent native input covers the zone, so browsers handle file drops natively. */}
        <input
          id={id}
          type="file"
          className="dropzone__input"
          accept={ACCEPTED_FILE_TYPES.join(',')}
          disabled={isDisabled}
          aria-labelledby={`${id}-label`}
          aria-describedby={problem ? `${hintId} ${problemId}` : hintId}
          aria-invalid={problem ? true : undefined}
          onChange={handleInputChange}
          onDragEnter={() => setIsDragActive(true)}
          onDragLeave={() => setIsDragActive(false)}
          onDrop={() => setIsDragActive(false)}
        />
      </label>
      <p id={hintId} className="hint">
        {t('upload.acceptedTypes', { maxSize: MAX_UPLOAD_MEGABYTES })}
      </p>
      {selectedFileName && (
        <p className="hint hint--strong">{t('upload.selected', { fileName: selectedFileName })}</p>
      )}
      {problem && (
        <p id={problemId} role="alert" className="field-error">
          {t(`upload.${problem}`, { maxSize: MAX_UPLOAD_MEGABYTES })}
        </p>
      )}
    </div>
  );
};
