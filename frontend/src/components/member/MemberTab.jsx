import { useState, useEffect, useCallback } from 'react'
import { getMembers, getMember, getPolicies, getClaims, getClaim } from '../../api/client'
import MemberCard from './MemberCard'
import AccumulatorBars from './AccumulatorBars'
import CoverageRulesTable from './CoverageRulesTable'
import ClaimForm from './ClaimForm'
import ClaimDetail from '../shared/ClaimDetail'
import StatusBadge from '../shared/StatusBadge'
import TierBadge from '../shared/TierBadge'

const fmtDate = d => d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'

export default function MemberTab() {
  const [members, setMembers] = useState([])
  const [policies, setPolicies] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [memberDetail, setMemberDetail] = useState(null)
  const [claims, setClaims] = useState([])
  const [activeClaim, setActiveClaim] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getMembers(), getPolicies()])
      .then(([m, p]) => { setMembers(m); setPolicies(p) })
      .finally(() => setLoading(false))
  }, [])

  const loadMember = useCallback(async id => {
    setSelectedId(id); setActiveClaim(null); setShowForm(false)
    const [detail, claimList] = await Promise.all([getMember(id), getClaims(id)])
    setMemberDetail(detail)
    setClaims(claimList)
  }, [])

  const policy = policies.find(p => p.id === memberDetail?.policy_id)

  const refreshClaim = useCallback(async () => {
    if (!activeClaim) return
    const updated = await getClaim(activeClaim.id)
    setActiveClaim(updated)
    const claimList = await getClaims(selectedId)
    setClaims(claimList)
    if (selectedId) {
      const detail = await getMember(selectedId)
      setMemberDetail(detail)
    }
  }, [activeClaim, selectedId])

  const openClaim = async claim => {
    const full = await getClaim(claim.id)
    setActiveClaim(full); setShowForm(false)
  }

  if (loading) return <div style={{ padding: 40, color: 'var(--text-faint)', textAlign: 'center' }}>Loading…</div>

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 20, height: '100%' }}>
      {/* Left: member list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
          Members
        </div>
        {members.map(m => (
          <MemberCard key={m.id} member={m} selected={m.id === selectedId} onClick={() => loadMember(m.id)} />
        ))}
      </div>

      {/* Right: content */}
      <div>
        {!selectedId ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: 'var(--text-faint)', fontSize: 14 }}>
            Select a member to get started
          </div>
        ) : !memberDetail ? (
          <div style={{ color: 'var(--text-faint)', padding: 20 }}>Loading…</div>
        ) : activeClaim ? (
          <div className="card" style={{ padding: 20 }}>
            <ClaimDetail
              claim={activeClaim} isInsurer={false}
              onRefresh={refreshClaim}
              onBack={() => setActiveClaim(null)}
            />
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Member info */}
            <div className="card" style={{ padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                <div>
                  <h2 style={{ marginBottom: 4 }}>{memberDetail.name}</h2>
                  <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>
                    {memberDetail.member_number} · Enrolled {fmtDate(memberDetail.enrollment_date)}
                  </div>
                </div>
                <TierBadge tier={memberDetail.policy_tier} />
              </div>
              <hr className="divider" />
              <AccumulatorBars member={memberDetail} policy={policy} />
              <hr className="divider" />
              <CoverageRulesTable policy={policy} />
            </div>

            {/* Claims history */}
            <div className="card" style={{ padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                <h3>Claims History</h3>
                <button className="btn-primary btn-sm" onClick={() => setShowForm(true)}>+ New Claim</button>
              </div>
              {claims.length === 0 ? (
                <div style={{ color: 'var(--text-faint)', fontSize: 13, textAlign: 'center', padding: '16px 0' }}>
                  No claims yet. Submit your first claim above.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {claims.map(c => (
                    <div key={c.id}
                      onClick={() => openClaim(c)}
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer', transition: 'background 0.1s',
                        background: 'var(--surface)',
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = '#faf7f4'}
                      onMouseLeave={e => e.currentTarget.style.background = 'var(--surface)'}
                    >
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{c.claim_number}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>
                          {c.provider_name} · {fmtDate(c.submission_date)} · {c.line_items?.length || 0} item{c.line_items?.length !== 1 ? 's' : ''}
                        </div>
                      </div>
                      <StatusBadge status={c.status} small />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {showForm && memberDetail && (
        <ClaimForm
          member={memberDetail}
          onClose={() => setShowForm(false)}
          onSubmitted={async claim => {
            setShowForm(false)
            const [detail, claimList] = await Promise.all([getMember(selectedId), getClaims(selectedId)])
            setMemberDetail(detail); setClaims(claimList)
            setActiveClaim(claim)
          }}
        />
      )}
    </div>
  )
}
