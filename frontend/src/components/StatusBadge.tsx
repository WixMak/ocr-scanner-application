import { CircleCheck, CircleMinus, PencilLine, TriangleAlert, type LucideIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { FieldStatus } from '../api/schemas';

export type DisplayStatus = FieldStatus | 'edited';

const STATUS_ICONS: Record<DisplayStatus, LucideIcon> = {
  confirmed: CircleCheck,
  review: TriangleAlert,
  empty: CircleMinus,
  edited: PencilLine,
};

export const StatusBadge = ({ status }: { status: DisplayStatus }) => {
  const { t } = useTranslation();
  const Icon = STATUS_ICONS[status];

  return (
    <span className={`status-badge status-badge--${status}`}>
      <Icon aria-hidden="true" className="icon icon--sm" />
      {t(`fieldStatus.${status}`)}
    </span>
  );
};
