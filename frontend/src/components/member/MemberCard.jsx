import TierBadge from '../shared/TierBadge'

export default function MemberCard({ member, selected, onClick }) {
  const initials = member.name.split(' ').map(w => w[0]).join('')
  return (
    <div
      onClick={onClick}
      style={{
        background: selected ? 'var(--surface)' : 'var(--surface)',
        border: selected ? '2px solid var(--red)' : '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        padding: '14px 16px',
        cursor: 'pointer',
        boxShadow: selected ? '0 0 0 3px var(--red-light)' : 'var(--shadow)',
        transition: 'all 0.15s',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 36, height: 36, borderRadius: '50%',
          background: selected ? 'var(--red)' : '#e8e0d8',
          color: selected ? '#fff' : 'var(--text-muted)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontWeight: 700, fontSize: 13, flexShrink: 0,
        }}>
          {initials}
        </div>
        <div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{member.name}</div>
          <div style={{ fontSize: 11, color: 'var(--text-faint)' }}>{member.member_number}</div>
        </div>
      </div>
      <TierBadge tier={member.policy_tier} />
    </div>
  )
}
