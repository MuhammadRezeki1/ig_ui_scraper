'use client'

interface IGLogoProps {
  size?: number
  className?: string
  animated?: boolean
}

export function IGLogo({ size = 32, className = '', animated = false }: IGLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      className={`${animated ? 'animate-spin-slow' : ''} ${className}`}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="ig-grad-logo" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%"   stopColor="#FCAF45"/>
          <stop offset="20%"  stopColor="#F77737"/>
          <stop offset="40%"  stopColor="#F56040"/>
          <stop offset="55%"  stopColor="#E1306C"/>
          <stop offset="70%"  stopColor="#C13584"/>
          <stop offset="85%"  stopColor="#833AB4"/>
          <stop offset="100%" stopColor="#405DE6"/>
        </linearGradient>
      </defs>
      {/* Outer rounded rect */}
      <rect x="3" y="3" width="42" height="42" rx="13" stroke="url(#ig-grad-logo)" strokeWidth="3" fill="none"/>
      {/* Inner circle */}
      <circle cx="24" cy="24" r="9.5" stroke="url(#ig-grad-logo)" strokeWidth="3" fill="none"/>
      {/* Dot */}
      <circle cx="34.5" cy="13.5" r="2.5" fill="url(#ig-grad-logo)"/>
    </svg>
  )
}

export function IGLogoFilled({ size = 32, className = '' }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="ig-fill-grad" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%"   stopColor="#FCAF45"/>
          <stop offset="25%"  stopColor="#F77737"/>
          <stop offset="45%"  stopColor="#E1306C"/>
          <stop offset="70%"  stopColor="#C13584"/>
          <stop offset="85%"  stopColor="#833AB4"/>
          <stop offset="100%" stopColor="#405DE6"/>
        </linearGradient>
        <linearGradient id="ig-fill-inner" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%"   stopColor="#FCAF45"/>
          <stop offset="50%"  stopColor="#E1306C"/>
          <stop offset="100%" stopColor="#405DE6"/>
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="48" height="48" rx="14" fill="url(#ig-fill-grad)"/>
      <rect x="4" y="4" width="40" height="40" rx="11" stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" fill="none"/>
      <circle cx="24" cy="24" r="9" stroke="white" strokeWidth="3" fill="none"/>
      <circle cx="34.5" cy="13.5" r="2.5" fill="white"/>
    </svg>
  )
}
