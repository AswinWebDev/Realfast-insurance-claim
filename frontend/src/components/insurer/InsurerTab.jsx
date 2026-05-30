import { useState, useEffect, useCallback } from 'react'
import { getClaims, getClaim, getMembers } from '../../api/client'
import ClaimDetail from '../shared/ClaimDetail'
import StatusBadge from '../shared/StatusBadge'

const FILTERS = ['ALL', 'UNDER_REVIEW', 'DISPUTED', 'APPROVED', 'PARTIALLY_APPROVED', 'DENIED', 'PAID']
const fmtDate = d => d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'
const fmt = v => v != null ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'

export default function InsurerTab() {
  const [allClaims, setAllClaims] = useState([])
  const [members, setMembers] = useState([])
  const [filter, setFilter] = useState('ALL')
  const [activeClaim, setActiveClaim] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadAll = useCallback(async () => {
    const [m, claims] = await Promise.all([
      getMembers(),
      getClaims().catch(() => []),
    ])
    // getClaims() with no member_id returns all claims
    setMembers(m)
    setAllClaims(claims)
    setLoading(false)
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  // Poll every 5s for new claims while on this tab
  useEffect(() => {
    const t = setInterval(loadAll, 5000)
    return () => clearInterval(t)
  }, [loadAll])

  const refreshActive = useCallback(async () => {
    if (!activeClaim) return
    const updated = await getClaim(activeClaim.id)
    setActiveClaim(updated)
    loadAll()
  }, [activeClaim, loadAll])

  const getMemberName = id => members.find(m => m.id === id)?.name || id
  const getMemberTier = id => members.find(m => m.id === id)?.policy_tier || ''

  const filtered = filter === 'ALL' ? allClaims : allClaims.filter(c => {
    if (filter === 'UNDER_REVIEW')
      return c.status === 'UNDER_REVIEW' || c.line_items?.some(l => l.status === 'NEEDS_REVIEW')
    return c.status === filter
  })

  const counts = {
    // Claims needing manual action — either awaiting review or has a line item requiring prior auth decision
    NEEDS_MANUAL: allClaims.filter(c => c.line_items?.some(l => l.status === 'NEEDS_REVIEW')).length,
    // Claims under review that don't need manual action yet (e.g. awaiting info)
    UNDER_REVIEW: allClaims.filter(c => c.status === 'UNDER_REVIEW').length,
    DISPUTED: allClaims.filter(c => c.status === 'DISPUTED').length,
  }

  const TIER_COLOR = { DIAMOND: '#1d4ed8', GOLD: '#b45309', BRONZE: '#78350f' }

  if (loading) return <div style={{ padding: 40, color: 'var(--text-faint)', textAlign: 'center' }}>Loading…</div>

  return (
    <div style={{ display: 'grid', gridTemplateColumns: activeClaim ? '360px 1fr' : '1fr', gap: 20, height: '100%' }}>
      {/* Claims list */}
      <div>
        {/* Stats row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
          {[
            { label: 'Needs Manual Action', count: counts.NEEDS_MANUAL, color: 'var(--amber)', bg: 'rgba(180,83,9,0.07)' },
            { label: 'Disputed', count: counts.DISPUTED, color: '#7c3aed', bg: 'rgba(124,58,237,0.07)' },
            { label: 'Under Review', count: counts.UNDER_REVIEW, color: 'var(--blue)', bg: 'var(--blue-light)' },
          ].map(({ label, count, color, bg }) => (
            <div key={label} style={{ background: bg, border: `1px solid ${color}33`, borderRadius: 'var(--radius-sm)', padding: '10px 14px', textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 700, color }}>{count}</div>
              <div style={{ fontSize: 11, color, fontWeight: 600 }}>{label}</div>
            </div>
          ))}
        </div>

        {/* Filter tabs */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap' }}>
          {FILTERS.map(f => (
            <button key={f} onClick={() => setFilter(f)}
              style={{
                padding: '4px 12px', fontSize: 12, fontWeight: 600,
                borderRadius: 20, border: 'none',
                background: filter === f ? 'var(--red)' : 'var(--surface)',
                color: filter === f ? '#fff' : 'var(--text-muted)',
                boxShadow: 'var(--shadow)',
                cursor: 'pointer',
              }}>
              {f.replace(/_/g, ' ')}
              {f === 'UNDER_REVIEW' && counts.UNDER_REVIEW > 0 && (
                <span style={{ marginLeft: 5, background: filter === f ? 'rgba(255,255,255,0.3)' : 'var(--red)', color: '#fff', borderRadius: 20, padding: '0 5px', fontSize: 10 }}>
                  {counts.UNDER_REVIEW}
                </span>
              )}
              {f === 'DISPUTED' && counts.DISPUTED > 0 && (
                <span style={{ marginLeft: 5, background: filter === f ? 'rgba(255,255,255,0.3)' : 'var(--red)', color: '#fff', borderRadius: 20, padding: '0 5px', fontSize: 10 }}>
                  {counts.DISPUTED}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Claims table */}
        {filtered.length === 0 ? (
          <div style={{ color: 'var(--text-faint)', fontSize: 13, textAlign: 'center', padding: '30px 0' }}>
            No claims in this view
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {filtered.map(c => {
              const totalApproved = c.line_items?.reduce((s, l) => s + parseFloat(l.approved_amount || 0), 0) || 0
              const hasNeedsReview = c.line_items?.some(l => l.status === 'NEEDS_REVIEW')
              const tier = getMemberTier(c.member_id)
              return (
                <div key={c.id}
                  onClick={async () => { const full = await getClaim(c.id); setActiveClaim(full) }}
                  style={{
                    padding: '12px 14px', border: activeClaim?.id === c.id ? '2px solid var(--red)' : '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)', cursor: 'pointer', background: 'var(--surface)',
                    transition: 'background 0.1s', boxShadow: 'var(--shadow)',
                  }}
                  onMouseEnter={e => { if (activeClaim?.id !== c.id) e.currentTarget.style.background = '#faf7f4' }}
                  onMouseLeave={e => { if (activeClaim?.id !== c.id) e.currentTarget.style.background = 'var(--surface)' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 700, fontSize: 13 }}>{c.claim_number}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                        <span style={{ fontWeight: 600 }}>{getMemberName(c.member_id)}</span>
                        {tier && <span style={{ marginLeft: 6, fontWeight: 600, fontSize: 10, color: TIER_COLOR[tier] }}>{tier}</span>}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>
                        {c.provider_name} · {fmtDate(c.submission_date)}
                      </div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
                      <StatusBadge status={c.status} small />
                      {hasNeedsReview && <StatusBadge status="NEEDS_REVIEW" small />}
                      <div style={{ fontSize: 12, color: 'var(--green)', fontWeight: 600 }}>{fmt(totalApproved)}</div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Claim detail pane */}
      {activeClaim && (
        <div className="card" style={{ padding: 20, alignSelf: 'flex-start', position: 'sticky', top: 20 }}>
          <ClaimDetail
            claim={activeClaim} isInsurer={true}
            onRefresh={refreshActive}
            onBack={() => setActiveClaim(null)}
          />
        </div>
      )}
    </div>
  )
}
