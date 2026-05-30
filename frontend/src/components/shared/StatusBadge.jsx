const MAP = {
  SUBMITTED:          { label: 'Submitted',          color: '#666', bg: '#f0eded' },
  UNDER_REVIEW:       { label: 'Under Review',        color: '#b45309', bg: 'rgba(180,83,9,0.09)' },
  APPROVED:           { label: 'Approved',            color: '#1a7a4a', bg: 'rgba(26,122,74,0.09)' },
  PARTIALLY_APPROVED: { label: 'Partially Approved',  color: '#1d4ed8', bg: 'rgba(29,78,216,0.08)' },
  DENIED:             { label: 'Denied',              color: 'rgb(226,54,54)', bg: 'rgba(226,54,54,0.08)' },
  PAID:               { label: 'Paid',                color: '#1a7a4a', bg: 'rgba(26,122,74,0.14)' },
  DISPUTED:           { label: 'Disputed',            color: '#7c3aed', bg: 'rgba(124,58,237,0.08)' },
  UPHELD:             { label: 'Upheld',              color: '#666', bg: '#f0eded' },
  OVERTURNED:         { label: 'Overturned',          color: '#1a7a4a', bg: 'rgba(26,122,74,0.09)' },
  PENDING:            { label: 'Pending',             color: '#666', bg: '#f0eded' },
  NEEDS_REVIEW:       { label: 'Needs Review',        color: '#b45309', bg: 'rgba(180,83,9,0.09)' },
  OPEN:               { label: 'Open',                color: '#b45309', bg: 'rgba(180,83,9,0.09)' },
}

export default function StatusBadge({ status, small }) {
  const s = MAP[status] || { label: status, color: '#666', bg: '#f0eded' }
  return (
    <span style={{
      display: 'inline-block',
      padding: small ? '1px 7px' : '2px 9px',
      borderRadius: 20,
      fontSize: small ? 11 : 12,
      fontWeight: 600,
      color: s.color,
      background: s.bg,
      letterSpacing: '0.02em',
      whiteSpace: 'nowrap',
    }}>
      {s.label}
    </span>
  )
}
