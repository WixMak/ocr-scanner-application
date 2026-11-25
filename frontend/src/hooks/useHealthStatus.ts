import { useQuery } from '@tanstack/react-query';
import { getHealth } from '../api/formScannerApi';

const HEALTH_REFRESH_INTERVAL_MS = 30_000;

export const useHealthStatus = () =>
  useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: HEALTH_REFRESH_INTERVAL_MS,
  });
