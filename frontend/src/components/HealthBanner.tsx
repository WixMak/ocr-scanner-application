import { TriangleAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { HealthStatus } from '../api/schemas';
import { useHealthStatus } from '../hooks/useHealthStatus';

const listHealthProblems = (health: HealthStatus): { key: string; model?: string }[] => {
  if (!health.isOllamaReachable) {
    return [{ key: 'health.ollamaUnreachable' }];
  }
  return [health.fastModel, health.accurateModel]
    .filter((engine) => !engine.isAvailable)
    .map((engine) => ({ key: 'health.modelMissing', model: engine.model }));
};

export const HealthBanner = () => {
  const { t } = useTranslation();
  const { data: health } = useHealthStatus();
  const problems = health ? listHealthProblems(health) : [];

  return (
    <div role="status" className="health-banner-region">
      {problems.length > 0 && (
        <div className="banner banner--warning">
          <TriangleAlert aria-hidden="true" className="icon icon--md banner__icon" />
          <ul className="banner__list">
            {problems.map((problem) => (
              <li key={`${problem.key}-${problem.model ?? ''}`}>
                {t(problem.key, { model: problem.model })}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
