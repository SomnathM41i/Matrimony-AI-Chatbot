import { useState, useEffect, useCallback } from 'react'
import { getHealth } from '../services/healthService'

export function useDatabaseStatus() {
  const [dbConnected, setDbConnected] = useState(null)
  const [llm, setLlm] = useState(null)
  const [loading, setLoading] = useState(true)

  const check = useCallback(async () => {
    try {
      const data = await getHealth()
      setDbConnected(data.database === 'connected')
      setLlm(data.llm || null)
    } catch {
      setDbConnected(false)
      setLlm(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    check()
    const interval = setInterval(check, 30000)
    return () => clearInterval(interval)
  }, [check])

  return { dbConnected, llm, loading }
}
