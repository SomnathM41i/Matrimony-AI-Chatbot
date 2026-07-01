import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getConversations,
  deleteConversation,
  updateConversation,
} from '../services/chatService'

export function useHistory() {
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['conversations'],
    queryFn: () => getConversations(1, 50),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteConversation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
  })

  const renameMutation = useMutation({
    mutationFn: ({ id, title }) => updateConversation(id, { title }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
  })

  return {
    conversations: data?.items || [],
    total: data?.total || 0,
    isLoading,
    deleteConversation: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,
    renameConversation: renameMutation.mutateAsync,
    isRenaming: renameMutation.isPending,
  }
}
