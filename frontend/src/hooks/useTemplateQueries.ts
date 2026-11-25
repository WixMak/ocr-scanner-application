import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createTemplate,
  createTemplateDraft,
  deleteTemplate,
  getTemplate,
  listTemplates,
  updateTemplate,
} from '../api/formScannerApi';
import type { Template, TemplateInput } from '../api/schemas';

export const templateQueryKeys = {
  all: ['templates'] as const,
  list: () => [...templateQueryKeys.all, 'list'] as const,
  detail: (templateId: string) => [...templateQueryKeys.all, 'detail', templateId] as const,
};

export const useTemplateList = () =>
  useQuery({ queryKey: templateQueryKeys.list(), queryFn: listTemplates });

export const useTemplate = (templateId: string) =>
  useQuery({
    queryKey: templateQueryKeys.detail(templateId),
    queryFn: () => getTemplate(templateId),
  });

export const useCreateTemplateDraft = () => useMutation({ mutationFn: createTemplateDraft });

export type SaveTemplateTarget =
  | { kind: 'draft'; draftId: string }
  | { kind: 'saved'; templateId: string };

export const useSaveTemplate = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ target, input }: { target: SaveTemplateTarget; input: TemplateInput }) =>
      target.kind === 'draft'
        ? createTemplate(target.draftId, input)
        : updateTemplate(target.templateId, input),
    onSuccess: (template: Template) => {
      queryClient.setQueryData(templateQueryKeys.detail(template.id), template);
      return queryClient.invalidateQueries({ queryKey: templateQueryKeys.list() });
    },
  });
};

export const useDeleteTemplate = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: templateQueryKeys.list() }),
  });
};
