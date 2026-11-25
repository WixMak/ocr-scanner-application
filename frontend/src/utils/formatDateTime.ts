import dayjs from 'dayjs';

const TIME_FORMAT = 'HH:mm:ss';
const DATE_TIME_FORMAT = 'YYYY-MM-DD HH:mm';
const FILE_TIMESTAMP_FORMAT = 'YYYYMMDD-HHmmss';

export const formatTime = (isoTimestamp: string): string => dayjs(isoTimestamp).format(TIME_FORMAT);

export const formatDateTime = (isoTimestamp: string): string =>
  dayjs(isoTimestamp).format(DATE_TIME_FORMAT);

export const formatFileTimestamp = (): string => dayjs().format(FILE_TIMESTAMP_FORMAT);
