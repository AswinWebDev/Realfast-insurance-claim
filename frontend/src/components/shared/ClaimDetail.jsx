import { useState } from 'react'
import StatusBadge from './StatusBadge'
import { updateClaimStatus, resolveReview, fileDispute, resolveDispute } from '../../api/client'

const fmt = v => v != null ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'
const fmtDate = d => d ? new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'

const SVC_LABELS = {
  PRIMARY_CARE: 'Primary Care', SPECIALIST: 'Specialist', EMERGENCY_ROOM: 'Emergency Room',
  URGENT_CARE: 'Urgent Care', INPATIENT: 'Inpatient', OUTPATIENT_SURGERY: 'Outpatient Surgery',
  LAB: 'Lab', IMAGING: 'Imaging', PRESCRIPTION: 'Prescription',
  PHYSICAL_THERAPY: 'Physical Therapy', MENTAL_HEALTH: 'Mental Health',
}

function AdjNotes({ notes }) {
  const [open, setOpen] = useState(false)
  if (!notes) return null
  return (
    <div style={{ marginTop: 4 }}>
      <button className="btn-ghost btn-sm" onClick={() => setOpen(o => !o)}
        style={{ padding: '2px 0', fontSize: 11, color: 'var(--text-muted)' }}>
        {open ? '▾' : '▸'} adjudication notes
      </button>
      {open && (
        <pre style={{
          marginTop: 6, padding: '10px 12px', background: '#faf7f4',
          border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
          fontSize: 11, lineHeight: 1.6, whiteSpace: 'pre-wrap', color: 'var(--text-muted)',
          fontFamily: 'ui-monospace, monospace',
        }}>
          {notes}
        </pre>
      )}
    </div>
  )
}

function DisputeRow({ dispute, claimId, lineItemId, isInsurer, onRefresh }) {
  const [loading, setLoading] = useState(false)
  const [notes, setNotes] = useState('')
  const [showResolve, setShowResolve] = useState(false)

  const resolve = async outcome => {
    if (!notes.trim()) return
    setLoading(true)
    try { await resolveDispute(claimId, lineItemId, dispute.id, outcome, notes); onRefresh() }
    catch (e) { alert(e.response?.data?.detail || 'Failed') }
    finally { setLoading(false) }
  }

  return (
    <div style={{ background: 'rgba(124,58,237,0.05)', border: '1px solid rgba(124,58,237,0.15)', borderRadius: 'var(--radius-sm)', padding: '10px 12px', marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontWeight: 600, fontSize: 12, color: '#7c3aed' }}>Dispute</span>
        <StatusBadge status={dispute.status} small />
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>{dispute.reason}</p>
      {dispute.resolution_notes && <p style={{ fontSize: 12, color: 'var(--text-faint)', fontStyle: 'italic' }}>{dispute.resolution_notes}</p>}
      {isInsurer && dispute.status === 'OPEN' && (
        showResolve ? (
          <div style={{ marginTop: 8 }}>
            <textarea rows={2} value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="Resolution notes (required)…"
              style={{ marginBottom: 8, fontSize: 12, resize: 'vertical' }} />
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn-success btn-sm" disabled={loading || !notes.trim()} onClick={() => resolve('OVERTURNED')}>Overturn</button>
              <button className="btn-danger btn-sm" disabled={loading || !notes.trim()} onClick={() => resolve('UPHELD')}>Uphold</button>
              <button className="btn-ghost btn-sm" onClick={() => setShowResolve(false)}>Cancel</button>
            </div>
          </div>
        ) : (
          <button className="btn-secondary btn-sm" style={{ marginTop: 8, fontSize: 12 }} onClick={() => setShowResolve(true)}>Resolve Dispute</button>
        )
      )}
    </div>
  )
}

function LineItemRow({ li, claimId, isInsurer, onRefresh, memberId }) {
  const [expanded, setExpanded] = useState(false)
  const [showDispute, setShowDispute] = useState(false)
  const [disputeReason, setDisputeReason] = useState('')
  const [reviewNotes, setReviewNotes] = useState('')
  const [showReview, setShowReview] = useState(false)
  const [loading, setLoading] = useState(false)

  const hasOpenDispute = li.disputes?.some(d => d.status === 'OPEN')
  const hasResolvedDispute = li.disputes?.some(d => d.status === 'UPHELD' || d.status === 'OVERTURNED')

  const handleDispute = async () => {
    if (!disputeReason.trim()) return
    setLoading(true)
    try { await fileDispute(claimId, li.id, disputeReason); onRefresh() }
    catch (e) { alert(e.response?.data?.detail || 'Failed') }
    finally { setLoading(false); setShowDispute(false) }
  }

  const handleReview = async outcome => {
    setLoading(true)
    try { await resolveReview(claimId, li.id, outcome, reviewNotes || 'Manual review decision'); onRefresh() }
    catch (e) { alert(e.response?.data?.detail || 'Failed') }
    finally { setLoading(false); setShowReview(false) }
  }

  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
      overflow: 'hidden', marginBottom: 8,
    }}>
      {/* Main row */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr auto auto auto auto',
        gap: 12, alignItems: 'center', padding: '10px 14px',
        background: li.status === 'DENIED' ? 'rgba(226,54,54,0.03)' : 'var(--surface)',
      }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{SVC_LABELS[li.service_type] || li.service_type}</div>
          <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>{fmtDate(li.service_date)}{li.procedure_code ? ` · ${li.procedure_code}` : ''}{li.diagnosis_code ? ` · ${li.diagnosis_code}` : ''}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>Billed</div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{fmt(li.billed_amount)}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>Insurance Pays</div>
          <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--green)' }}>{fmt(li.approved_amount)}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>You Pay</div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{fmt(li.member_responsibility)}</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          <StatusBadge status={li.status} small />
          <button className="btn-ghost btn-sm" onClick={() => setExpanded(o => !o)} style={{ fontSize: 11 }}>
            {expanded ? '▴ Less' : '▾ More'}
          </button>
        </div>
      </div>

      {/* Expanded section */}
      {expanded && (
        <div style={{ padding: '12px 14px', borderTop: '1px solid var(--border)', background: '#faf7f4' }}>
          {li.denial_reason && (
            <div style={{
              background: 'var(--red-light)', border: '1px solid var(--red-mid)',
              borderRadius: 'var(--radius-sm)', padding: '8px 12px', marginBottom: 10, fontSize: 12, color: 'var(--red)',
            }}>
              <strong>Denial Reason:</strong> {li.denial_reason}
            </div>
          )}

          <AdjNotes notes={li.adjudication_notes} />

          {/* Disputes */}
          {li.disputes?.length > 0 && li.disputes.map(d => (
            <DisputeRow key={d.id} dispute={d} claimId={claimId} lineItemId={li.id} isInsurer={isInsurer} onRefresh={onRefresh} />
          ))}

          {/* File dispute — member side */}
          {!isInsurer && (li.status === 'DENIED' || li.status === 'APPROVED') && !hasOpenDispute && !hasResolvedDispute && (
            showDispute ? (
              <div style={{ marginTop: 10 }}>
                <label>Reason for Dispute</label>
                <textarea rows={2} value={disputeReason} onChange={e => setDisputeReason(e.target.value)}
                  placeholder="Explain why you are disputing this decision…" style={{ marginBottom: 8, resize: 'vertical', fontSize: 12 }} />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn-danger btn-sm" disabled={loading || disputeReason.length < 10} onClick={handleDispute}>
                    {loading ? 'Filing…' : 'File Dispute'}
                  </button>
                  <button className="btn-ghost btn-sm" onClick={() => setShowDispute(false)}>Cancel</button>
                </div>
              </div>
            ) : (
              <button className="btn-secondary btn-sm" style={{ marginTop: 10 }} onClick={() => setShowDispute(true)}>
                File Dispute
              </button>
            )
          )}

          {/* Insurer: resolve NEEDS_REVIEW */}
          {isInsurer && li.status === 'NEEDS_REVIEW' && (
            showReview ? (
              <div style={{ marginTop: 10 }}>
                <label>Review Notes</label>
                <input value={reviewNotes} onChange={e => setReviewNotes(e.target.value)} placeholder="e.g. Prior auth confirmed on file" style={{ marginBottom: 8 }} />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn-success btn-sm" disabled={loading} onClick={() => handleReview('APPROVED')}>Approve</button>
                  <button className="btn-danger btn-sm" disabled={loading} onClick={() => handleReview('DENIED')}>Deny</button>
                  <button className="btn-ghost btn-sm" onClick={() => setShowReview(false)}>Cancel</button>
                </div>
              </div>
            ) : (
              <button className="btn-blue btn-sm" style={{ marginTop: 10 }} onClick={() => setShowReview(true)}>
                Manual Review
              </button>
            )
          )}
        </div>
      )}
    </div>
  )
}

export default function ClaimDetail({ claim, isInsurer, onRefresh, onBack }) {
  const [loading, setLoading] = useState(false)

  const canPay = isInsurer && ['APPROVED', 'PARTIALLY_APPROVED'].includes(claim.status)

  const markPaid = async () => {
    setLoading(true)
    try { await updateClaimStatus(claim.id, 'PAID'); onRefresh() }
    catch (e) { alert(e.response?.data?.detail || 'Failed') }
    finally { setLoading(false) }
  }

  const totalBilled = claim.line_items?.reduce((s, l) => s + parseFloat(l.billed_amount || 0), 0) || 0
  const totalApproved = claim.line_items?.reduce((s, l) => s + parseFloat(l.approved_amount || 0), 0) || 0
  const totalMember = claim.line_items?.reduce((s, l) => s + parseFloat(l.member_responsibility || 0), 0) || 0
  const totalAboveLimit = Math.max(0, totalBilled - totalApproved - totalMember)

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 10 }}>
        <div>
          {onBack && (
            <button className="btn-ghost btn-sm" onClick={onBack} style={{ marginBottom: 6, padding: '2px 0', fontSize: 12 }}>
              ← Back to claims
            </button>
          )}
          <div style={{ fontWeight: 700, fontSize: 16 }}>{claim.claim_number}</div>
          <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>
            {claim.provider_name} · {fmtDate(claim.submission_date)}
          </div>
          {claim.notes && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, fontStyle: 'italic' }}>{claim.notes}</div>}
        </div>
        <StatusBadge status={claim.status} />
      </div>

      {/* Summary totals */}
      <div style={{ display: 'grid', gridTemplateColumns: totalAboveLimit > 0 ? 'repeat(4, 1fr)' : 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
        {[
          { label: 'Total Billed', value: fmt(totalBilled), color: 'var(--text)' },
          { label: 'Insurance Pays', value: fmt(totalApproved), color: 'var(--green)' },
          { label: 'Member Pays', value: fmt(totalMember), color: 'var(--red)' },
          ...(totalAboveLimit > 0 ? [{ label: 'Above Limit (Provider Write-off)', value: fmt(totalAboveLimit), color: 'var(--text-faint)' }] : []),
        ].map(({ label, value, color }) => (
          <div key={label} style={{ background: '#faf7f4', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '10px 14px', textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: 'var(--text-faint)', marginBottom: 3 }}>{label}</div>
            <div style={{ fontWeight: 700, fontSize: 16, color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Line items */}
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
          Line Items ({claim.line_items?.length || 0})
        </div>
        {claim.line_items?.map(li => (
          <LineItemRow
            key={li.id} li={li} claimId={claim.id}
            isInsurer={isInsurer} onRefresh={onRefresh}
            memberId={claim.member_id}
          />
        ))}
      </div>

      {/* Actions — insurer only: Mark as Paid */}
      {isInsurer && canPay && (
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-success" disabled={loading} onClick={markPaid}>Mark as Paid</button>
        </div>
      )}
    </div>
  )
}
