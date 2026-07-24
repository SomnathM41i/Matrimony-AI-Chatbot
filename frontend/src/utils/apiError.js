const FALLBACK_ERROR_MESSAGE = 'Sorry, I encountered an error.'

export function getApiErrorMessage(error, fallback = FALLBACK_ERROR_MESSAGE) {
  const detail = error?.response?.data?.detail

  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }

  if (typeof detail?.message === 'string' && detail.message.trim()) {
    return detail.message
  }

  if (typeof error?.message === 'string' && error.message.trim()) {
    return error.message
  }

  return fallback
}
