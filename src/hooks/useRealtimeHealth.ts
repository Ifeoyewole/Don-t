import { useCallback, useEffect, useRef, useState } from 'react'
import { checkBackendHealth, type BackendHealthResult } from '../lib/cvClient'

export interface RealtimeHealthState extends BackendHealthResult {
  isChecking: boolean
  lastChecked?: Date
}

export function useRealtimeHealth(pollIntervalMs = 20000) {
  const [health, setHealth] = useState<RealtimeHealthState>({
    online: typeof window !== 'undefined' ? window.navigator.onLine : true,
    cloudConnected: false,
    modelReady: true,
    source: 'local',
    isChecking: true,
  })

  const inFlightRef = useRef(false)

  const checkNow = useCallback(async () => {
    if (inFlightRef.current) return
    inFlightRef.current = true
    setHealth((prev) => ({ ...prev, isChecking: true }))

    try {
      const res = await checkBackendHealth()
      setHealth({
        ...res,
        isChecking: false,
        lastChecked: new Date(),
      })
    } catch {
      setHealth((prev) => ({
        ...prev,
        isChecking: false,
        cloudConnected: false,
        lastChecked: new Date(),
      }))
    } finally {
      inFlightRef.current = false
    }
  }, [])

  useEffect(() => {
    const timerId = setTimeout(() => {
      void checkNow()
    }, 0)

    const intervalId = setInterval(() => {
      if (document.visibilityState === 'visible') {
        void checkNow()
      }
    }, pollIntervalMs)

    const handleOnline = () => void checkNow()
    const handleOffline = () => {
      setHealth((prev) => ({
        ...prev,
        online: false,
        cloudConnected: false,
        modelReady: false,
        source: 'offline',
        isChecking: false,
      }))
    }
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        void checkNow()
      }
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      clearTimeout(timerId)
      clearInterval(intervalId)
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [checkNow, pollIntervalMs])

  return { health, checkNow }
}
