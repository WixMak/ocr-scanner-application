import { CircleAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { ApiError, CLIENT_ERROR_CODES } from '../api/client';

const getErrorCode = (error: unknown): string =>
  error instanceof ApiError ? error.code : CLIENT_ERROR_CODES.unknown;

const getPageNumbers = (error: unknown): readonly number[] =>
  error instanceof ApiError ? error.pageNumbers : [];

export const ErrorAlert = ({ error, id }: { error: unknown; id?: string }) => {
  const { t, i18n } = useTranslation();
  const code = getErrorCode(error);
  const pageNumbers = getPageNumbers(error);
  const listFormatter = new Intl.ListFormat(i18n.language, { type: 'conjunction' });
  const messageKeys = [`errors.${code}`, `errors.${CLIENT_ERROR_CODES.unknown}`];
  const message =
    pageNumbers.length > 0
      ? t(messageKeys, {
          count: pageNumbers.length,
          pages: listFormatter.format(pageNumbers.map(String)),
        })
      : t(messageKeys);

  return (
    <div role="alert" id={id} className="banner banner--error">
      <CircleAlert aria-hidden="true" className="icon icon--md banner__icon" />
      <p>{message}</p>
    </div>
  );
};
