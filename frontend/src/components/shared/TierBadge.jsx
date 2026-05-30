const TIER = {
  DIAMOND: { label: 'Diamond', color: '#1d4ed8', bg: 'rgba(29,78,216,0.08)' },
  GOLD:    { label: 'Gold',    color: '#b45309', bg: 'rgba(180,83,9,0.09)' },
  BRONZE:  { label: 'Bronze',  color: '#78350f', bg: 'rgba(120,53,15,0.09)' },
}

export default function TierBadge({ tier }) {
  const t = TIER[tier] || { label: tier, color: '#666', bg: '#eee' }
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 9px',
      borderRadius: 20,
      fontSize: 11,
      fontWeight: 700,
      color: t.color,
      background: t.bg,
      letterSpacing: '0.04em',
      textTransform: 'uppercase',
    }}>
      {t.label}
    </span>
  )
}
