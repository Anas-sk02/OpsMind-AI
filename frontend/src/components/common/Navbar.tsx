import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { SimulateEmailModal } from './SimulateEmailModal';
import { Sparkles, LogOut, Zap } from 'lucide-react';
import type { UserRole } from '../../types';

interface NavbarProps {
  onRefresh?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onRefresh }) => {
  const { user, logout, quickSwitchRole } = useAuth();
  const [isSimulateOpen, setIsSimulateOpen] = useState(false);

  return (
    <>
      <header
        style={{
          height: 64,
          background: 'rgba(17, 24, 39, 0.85)',
          backdropFilter: 'blur(12px)',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 1.5rem',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 'var(--radius-md)',
                background: 'linear-gradient(135deg, #0284c7 0%, #818cf8 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                boxShadow: '0 0 12px rgba(56, 189, 248, 0.4)',
              }}
            >
              <Zap size={18} />
            </div>
            <div>
              <span
                style={{
                  fontFamily: 'var(--font-heading)',
                  fontWeight: 700,
                  fontSize: '1.125rem',
                  letterSpacing: '-0.03em',
                  background: 'linear-gradient(135deg, #f8fafc 0%, #94a3b8 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}
              >
                OpsMind
              </span>
              <span
                style={{
                  fontSize: '0.65rem',
                  fontWeight: 700,
                  color: 'var(--accent-cyan)',
                  marginLeft: '0.35rem',
                  textTransform: 'uppercase',
                  padding: '0.1rem 0.35rem',
                  borderRadius: 'var(--radius-sm)',
                  background: 'rgba(56, 189, 248, 0.12)',
                  border: '1px solid rgba(56, 189, 248, 0.25)',
                }}
              >
                AI Engine
              </span>
            </div>
          </div>
        </div>

        {/* Center / Right controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {/* Simulate Email Webhook Trigger */}
          <button
            onClick={() => setIsSimulateOpen(true)}
            className="btn btn-primary"
            style={{ fontSize: '0.8125rem', padding: '0.45rem 0.875rem' }}
          >
            <Sparkles size={14} />
            Simulate Inbound Email
          </button>

          {/* Quick Role Switcher for Developer Testing */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              background: 'rgba(0, 0, 0, 0.3)',
              borderRadius: 'var(--radius-md)',
              padding: '0.2rem',
              border: '1px solid var(--border-color)',
            }}
          >
            {(['ADMIN', 'PACKAGING', 'DELIVERY'] as UserRole[]).map((role) => {
              const isActive = user?.role === role;
              return (
                <button
                  key={role}
                  onClick={() => quickSwitchRole(role)}
                  style={{
                    padding: '0.3rem 0.6rem',
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    fontFamily: 'var(--font-heading)',
                    border: 'none',
                    borderRadius: 'var(--radius-sm)',
                    cursor: 'pointer',
                    background: isActive ? 'var(--accent-blue)' : 'transparent',
                    color: isActive ? '#fff' : 'var(--text-muted)',
                    transition: 'all 0.15s ease',
                  }}
                  title={`Switch role to ${role}`}
                >
                  {role === 'ADMIN' && 'Admin'}
                  {role === 'PACKAGING' && 'Packager'}
                  {role === 'DELIVERY' && 'Driver'}
                </button>
              );
            })}
          </div>

          {/* Current User Info & Logout */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              paddingLeft: '0.5rem',
              borderLeft: '1px solid var(--border-color)',
            }}
          >
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.8125rem', fontWeight: 600 }}>{user?.full_name}</div>
              <div
                style={{
                  fontSize: '0.7rem',
                  color: 'var(--accent-cyan)',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                }}
              >
                {user?.role}
              </div>
            </div>

            <button
              onClick={logout}
              className="btn btn-secondary btn-icon"
              title="Logout"
              style={{ borderRadius: 'var(--radius-md)', padding: '0.5rem' }}
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </header>

      <SimulateEmailModal
        isOpen={isSimulateOpen}
        onClose={() => setIsSimulateOpen(false)}
        onSuccess={() => {
          if (onRefresh) onRefresh();
        }}
      />
    </>
  );
};
