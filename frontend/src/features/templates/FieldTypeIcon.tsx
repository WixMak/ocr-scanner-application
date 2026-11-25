import { CalendarDays, Hash, ListChecks, Type, type LucideIcon } from 'lucide-react';
import type { FieldType } from '../../api/schemas';

const FIELD_TYPE_ICONS: Record<FieldType, LucideIcon> = {
  text: Type,
  number: Hash,
  date: CalendarDays,
  choice: ListChecks,
};

type FieldTypeIconProps = {
  fieldType: FieldType;
  className: string;
};

export const FieldTypeIcon = ({ fieldType, className }: FieldTypeIconProps) => {
  const Icon = FIELD_TYPE_ICONS[fieldType];

  return <Icon aria-hidden="true" className={`icon ${className}`} />;
};
