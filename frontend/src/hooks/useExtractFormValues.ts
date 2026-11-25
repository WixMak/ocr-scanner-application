import { useMutation } from '@tanstack/react-query';
import { extractFormValues } from '../api/formScannerApi';

export const useExtractFormValues = () =>
  useMutation({
    mutationFn: ({ templateId, file }: { templateId: string; file: File }) =>
      extractFormValues(templateId, file),
  });
