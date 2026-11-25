import { useTranslation } from 'react-i18next';

type PageSwitcherProps = {
  pageCount: number;
  currentPageIndex: number;
  onPageChange: (pageIndex: number) => void;
  getPageNumber?: (pageIndex: number) => number;
};

const toPageNumber = (pageIndex: number): number => pageIndex + 1;

export const PageSwitcher = ({
  pageCount,
  currentPageIndex,
  onPageChange,
  getPageNumber = toPageNumber,
}: PageSwitcherProps) => {
  const { t } = useTranslation();
  if (pageCount <= 1) {
    return null;
  }
  const pageIndexes = Array.from({ length: pageCount }, (_, pageIndex) => pageIndex);

  return (
    <div role="group" aria-label={t('pages.switcherLabel')} className="page-switcher">
      {pageIndexes.map((pageIndex) => (
        <button
          key={pageIndex}
          type="button"
          className="button button--secondary button--small page-switcher__button"
          aria-pressed={pageIndex === currentPageIndex}
          onClick={() => onPageChange(pageIndex)}
        >
          {t('pages.page', { number: getPageNumber(pageIndex) })}
        </button>
      ))}
    </div>
  );
};
