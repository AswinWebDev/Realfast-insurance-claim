function Bar({ label, used, total, color }) {
  const pct = total > 0 ? Math.min((used / total) * 100, 100) : 0
  const fmt = v => `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>{label}</span>
        <span style={{ fontSize: 12, color: 'var(--text-faint)' }}>
          <span style={{ color: 'var(--text)', fontWeight: 600 }}>{fmt(used)}</span> / {fmt(total)}
        </span>
      </div>
      <div style={{
        height: 7, background: '#ede7df', borderRadius: 4, overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: pct >= 90 ? 'var(--red)' : pct >= 60 ? 'var(--amber)' : color || 'var(--green)',
          borderRadius: 4,
          transition: 'width 0.4s ease',
        }} />
      </div>
    </div>
  )
}

const SVC_LABELS = {
  PRIMARY_CARE: 'Primary Care', SPECIALIST: 'Specialist', EMERGENCY_ROOM: 'Emergency Room',
  URGENT_CARE: 'Urgent Care', INPATIENT: 'Inpatient', OUTPATIENT_SURGERY: 'Outpatient Surgery',
  LAB: 'Lab', IMAGING: 'Imaging', PRESCRIPTION: 'Prescription',
  PHYSICAL_THERAPY: 'Physical Therapy', MENTAL_HEALTH: 'Mental Health',
}

export default function AccumulatorBars({ member, policy }) {
  if (!member || !policy) return null
  const accums = member.accumulators || []
  const year = new Date().getFullYear()

  const get = (type, svc = null) => {
    const a = accums.find(a => a.accumulator_type === type && a.service_type === svc && a.benefit_year === year)
    return parseFloat(a?.amount_used || 0)
  }

  const deductibleUsed = get('DEDUCTIBLE')
  const oopUsed = get('OOP_MAX')

  const svcBenefits = accums
    .filter(a => a.accumulator_type === 'SERVICE_BENEFIT' && a.benefit_year === year)
    .map(a => {
      const rule = policy.coverage_rules.find(r => r.service_type === a.service_type)
      return { svc: a.service_type, used: parseFloat(a.amount_used), limit: parseFloat(rule?.annual_limit || 0) }
    })
    .filter(a => a.limit > 0 && a.used > 0)

  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
        {year} Benefit Usage
      </div>
      <Bar label="Deductible" used={deductibleUsed} total={parseFloat(policy.annual_deductible)} color="var(--blue)" />
      <Bar label="Out-of-Pocket Max" used={oopUsed} total={parseFloat(policy.out_of_pocket_max)} color="var(--amber)" />
      {svcBenefits.length > 0 && (
        <>
          <div style={{ fontSize: 11, color: 'var(--text-faint)', margin: '10px 0 6px', fontWeight: 600 }}>BY SERVICE</div>
          {svcBenefits.map(a => (
            <Bar key={a.svc} label={SVC_LABELS[a.svc] || a.svc} used={a.used} total={a.limit} />
          ))}
        </>
      )}
      {deductibleUsed === 0 && oopUsed === 0 && svcBenefits.length === 0 && (
        <div style={{ color: 'var(--text-faint)', fontSize: 12, textAlign: 'center', padding: '10px 0' }}>
          No claims filed this year
        </div>
      )}
    </div>
  )
}
