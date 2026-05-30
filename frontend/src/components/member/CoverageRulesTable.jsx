import { useState } from 'react'

const SVC_LABELS = {
  PRIMARY_CARE: 'Primary Care', SPECIALIST: 'Specialist', EMERGENCY_ROOM: 'Emergency Room',
  URGENT_CARE: 'Urgent Care', INPATIENT: 'Inpatient', OUTPATIENT_SURGERY: 'Outpatient Surgery',
  LAB: 'Lab / Pathology', IMAGING: 'Imaging', PRESCRIPTION: 'Prescription',
  PHYSICAL_THERAPY: 'Physical Therapy', MENTAL_HEALTH: 'Mental Health',
}
const fmt = v => v != null ? `$${Number(v).toLocaleString()}` : '—'
const pct = v => v != null ? `${Math.round(v * 100)}%` : '—'

export default function CoverageRulesTable({ policy }) {
  const [open, setOpen] = useState(false)
  if (!policy) return null

  return (
    <div>
      <button
        className="btn-ghost btn-sm"
        onClick={() => setOpen(o => !o)}
        style={{ padding: '4px 0', fontSize: 12, color: 'var(--red)', fontWeight: 600 }}
      >
        {open ? '▾' : '▸'} Coverage Rules
      </button>
      {open && (
        <div style={{ marginTop: 10, overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: '#f5ede5' }}>
                {['Service', 'Annual Limit', 'Covered', 'Copay', 'Deductible', 'Prior Auth'].map(h => (
                  <th key={h} style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)', whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {policy.coverage_rules.map(r => (
                <tr key={r.id} style={{ borderBottom: '1px solid var(--border)', opacity: r.is_excluded ? 0.45 : 1 }}>
                  <td style={{ padding: '6px 10px', fontWeight: 500 }}>
                    {SVC_LABELS[r.service_type] || r.service_type}
                    {r.is_excluded && <span style={{ marginLeft: 6, fontSize: 10, color: 'var(--red)', fontWeight: 700 }}>EXCLUDED</span>}
                  </td>
                  <td style={{ padding: '6px 10px' }}>{r.is_excluded ? '—' : fmt(r.annual_limit)}</td>
                  <td style={{ padding: '6px 10px' }}>{r.is_excluded ? '—' : pct(r.covered_pct)}</td>
                  <td style={{ padding: '6px 10px' }}>{fmt(r.copay_amount)}</td>
                  <td style={{ padding: '6px 10px' }}>{r.deductible_applies ? 'Yes' : 'No'}</td>
                  <td style={{ padding: '6px 10px' }}>{r.requires_prior_auth ? <span style={{ color: 'var(--amber)', fontWeight: 600 }}>Required</span> : 'No'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
