import { useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../app/store'
import { getMe, login as loginApi, register as registerApi } from '../services/authService'
import { useNavigate } from 'react-router-dom'

export function useAuth() {
  const { token, user, setAuth, logout: storeLogout } = useAuthStore()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
    enabled: !!token && !user,
    retry: false,
    staleTime: 60000,
  })

  useEffect(() => {
    if (data) {
      useAuthStore.getState().setUser(data)
    }
  }, [data])

  useEffect(() => {
    if (isError && token) {
      storeLogout()
      queryClient.clear()
    }
  }, [isError, token, storeLogout, queryClient])

  const loginMutation = useMutation({
    mutationFn: ({ email, password }) => loginApi(email, password),
    onSuccess: (data) => {
      setAuth(data.access_token, data.user)
      navigate('/app/chat', { replace: true })
    },
  })

  const registerMutation = useMutation({
    mutationFn: ({ name, email, password }) => registerApi(name, email, password),
    onSuccess: (data) => {
      setAuth(data.access_token, data.user)
      navigate('/app/chat', { replace: true })
    },
  })

  const logout = () => {
    storeLogout()
    queryClient.clear()
    navigate('/login', { replace: true })
  }

  return {
    user: user || null,
    token,
    isLoading,
    login: loginMutation.mutateAsync,
    loginError: loginMutation.error,
    isLoginLoading: loginMutation.isPending,
    register: registerMutation.mutateAsync,
    registerError: registerMutation.error,
    isRegisterLoading: registerMutation.isPending,
    logout,
    isAuthenticated: !!token,
  }
}
