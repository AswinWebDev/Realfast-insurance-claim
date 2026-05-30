import { useState } from 'react'
import { submitClaim } from '../../api/client'
import Modal from '../shared/Modal'

const SERVICE_TYPES = [
  'PRIMARY_CARE', 'SPECIALIST', 'EMERGENCY_ROOM', 'URGENT_CARE',
  'INPATIENT', 'OUTPATIENT_SURGERY', 'LAB', 'IMAGING',
  'PRESCRIPTION', 'PHYSICAL_THERAPY', 'MENTAL_HEALTH',
]
const SVC_LABELS = {
  PRIMARY_CARE: 'Primary Care', SPECIALIST: 'Specialist', EMERGENCY_ROOM: 'Emergency Room',
  URGENT_CARE: 'Urgent Care', INPATIENT: 'Inpatient', OUTPATIENT_SURGERY: 'Outpatient Surgery',
  LAB: 'Lab / Pathology', IMAGING: 'Imaging', PRESCRIPTION: 'Prescription',
  PHYSICAL_THERAPY: 'Physical Therapy', MENTAL_HEALTH: 'Mental Health',
}

const emptyLine = () => ({
  service_type: 'PRIMARY_CARE',
  service_date: new Date().toISOString().slice(0, 10),
  billed_amount: '',
  procedure_code: '',
  diagnosis_code: '',
})

export default function ClaimForm({ member, onClose, onSubmitted }) {
  const [provider, setProvider] = useState('')
  const [lines, setLines] = useState([emptyLine()])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const updateLine = (i, field, val) =>
    setLines(ls => ls.map((l, idx) => idx === i ? { ...l, [field]: val } : l))

  const addLine = () => setLines(ls => [...ls, emptyLine()])
  const removeLine = i => setLines(ls => ls.filter((_, idx) => idx !== i))

  const handleSubmit = async e => {
    e.preventDefault()
    if (!provider.trim()) { setError('Provider name is required'); return }
    const lineItems = lines.map(l => ({
      service_type: l.service_type,
      service_date: l.service_date,
      billed_amount: parseFloat(l.billed_amount),
      procedure_code: l.procedure_code || undefined,
      diagnosis_code: l.diagnosis_code || undefined,
    }))
    if (lineItems.some(l => isNaN(l.billed_amount) || l.billed_amount <= 0)) {
      setError('All line items need a valid billed amount greater than $0')
      return
    }
    setLoading(true); setError(null)
    try {
      const claim = await submitClaim({ member_id: member.id, provider_name: provider, line_items: lineItems })
      onSubmitted(claim)
    } catch (e) {
      setError(e.response?.data?.detail || 'Submission failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="Submit New Claim" onClose={onClose} wide>
      <form onSubmit={handleSubmit}>
        {error && (
          <div style={{ background: 'var(--red-light)', border: '1px solid var(--red-mid)', borderRadius: 'var(--radius-sm)', padding: '10px 14px', marginBottom: 16, color: 'var(--red)', fontSize: 13 }}>
            {error}
          </div>
        )}

        <div style={{ marginBottom: 16 }}>
          <label>Provider / Clinic Name</label>
          <input value={provider} onChange={e => setProvider(e.target.value)} placeholder="e.g. Downtown Hospital" required />
        </div>

        <div style={{ borderBottom: '1px solid var(--border)', marginBottom: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
            Line Items
          </div>
          {lines.map((line, i) => (
            <div key={i} style={{
              background: '#faf7f4', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
              padding: '12px 14px', marginBottom: 10, position: 'relative',
            }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
                <div>
                  <label>Service Type</label>
                  <select value={line.service_type} onChange={e => updateLine(i, 'service_type', e.target.value)}>
                    {SERVICE_TYPES.map(s => <option key={s} value={s}>{SVC_LABELS[s]}</option>)}
                  </select>
                </div>
                <div>
                  <label>Service Date</label>
                  <input type="date" value={line.service_date} onChange={e => updateLine(i, 'service_date', e.target.value)} required />
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                <div>
                  <label>Billed Amount ($)</label>
                  <input type="number" min="0.01" step="0.01" value={line.billed_amount} onChange={e => updateLine(i, 'billed_amount', e.target.value)} placeholder="0.00" required />
                </div>
                <div>
                  <label>CPT Code (optional)</label>
                  <input value={line.procedure_code} onChange={e => updateLine(i, 'procedure_code', e.target.value)} placeholder="e.g. 99213" />
                </div>
                <div>
                  <label>ICD-10 Code (optional)</label>
                  <input value={line.diagnosis_code} onChange={e => updateLine(i, 'diagnosis_code', e.target.value)} placeholder="e.g. J06.9" />
                </div>
              </div>
              {lines.length > 1 && (
                <button type="button" onClick={() => removeLine(i)} className="btn-ghost btn-sm"
                  style={{ position: 'absolute', top: 8, right: 10, color: 'var(--red)', fontSize: 16, padding: '2px 8px' }}>
                  ×
                </button>
              )}
            </div>
          ))}
          <button type="button" className="btn-secondary btn-sm" onClick={addLine} style={{ marginBottom: 14 }}>
            + Add Line Item
          </button>
        </div>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Submitting…' : 'Submit Claim'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
