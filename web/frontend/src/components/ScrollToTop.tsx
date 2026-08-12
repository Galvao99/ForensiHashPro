import { useLayoutEffect } from 'react'
import { useLocation, useNavigationType } from 'react-router-dom'

export function ScrollToTop() {
  const { pathname, hash } = useLocation()
  const navigationType = useNavigationType()

  useLayoutEffect(() => {
    if (hash) {
      const target = document.getElementById(decodeURIComponent(hash.slice(1)))
      if (target) target.scrollIntoView()
      return
    }
    if (navigationType === 'POP') return
    window.scrollTo(0, 0)
  }, [hash, navigationType, pathname])

  return null
}
