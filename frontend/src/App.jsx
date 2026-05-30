import { useState } from 'react'
import MemberTab from './components/member/MemberTab'
import InsurerTab from './components/insurer/InsurerTab'

export default function App() {
  const [tab, setTab] = useState('member')

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <header style={{
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        padding: '0 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 52,
        position: 'sticky',
        top: 0,
        zIndex: 50,
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 28, height: 28, background: 'var(--red)', borderRadius: 6,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
          </div>
          <span style={{ fontWeight: 700, fontSize: 15, letterSpacing: '-0.01em' }}>RealFast Claims</span>
        </div>

        {/* Tab switcher */}
        <div style={{
          display: 'flex',
          background: '#f0e8e0',
          borderRadius: 8,
          padding: 3,
          gap: 2,
        }}>
          {[
            { key: 'member', label: 'Member View' },
            { key: 'insurer', label: 'Insurer View' },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              style={{
                padding: '5px 18px',
                fontSize: 13,
                fontWeight: 600,
                borderRadius: 6,
                border: 'none',
                background: tab === key ? 'var(--surface)' : 'transparent',
                color: tab === key ? 'var(--red)' : 'var(--text-muted)',
                boxShadow: tab === key ? 'var(--shadow)' : 'none',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <div style={{ width: 160 }} />
      </header>

      {/* Body */}
      <main style={{ flex: 1, padding: '24px 32px', maxWidth: 1200, width: '100%', margin: '0 auto', alignSelf: 'stretch', boxSizing: 'border-box' }}>
        {tab === 'member' ? <MemberTab /> : <InsurerTab />}
      </main>
    </div>
  )
}
