import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { SimulateEmailModal } from './SimulateEmailModal';
import { Sparkles, LogOut, Zap, Menu, X } from 'lucide-react';

interface NavbarProps {
  onRefresh?: () => void;
  onToggleMobileMenu?: () => void;
  isMobileMenuOpen?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  onRefresh,
  onToggleMobileMenu,
  isMobileMenuOpen,
}) => {
  const { user, logout } = useAuth();
  const [isSimulateOpen, setIsSimulateOpen] = useState(false);

  return (
    <>
      <header
        style={{
          height: 64,
          background: 'rgba(17, 24, 39, 0.85)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 1rem',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {/* Mobile Menu Toggle for Admin Role */}
          {user?.role === 'ADMIN' && onToggleMobileMenu && (
            <button
              onClick={onToggleMobileMenu}
              className="mobile-nav-toggle"
              aria-label={isMobileMenuOpen ? 'Close navigation' : 'Open navigation'}
            >
              {isMobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
            </button>
          )}

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
          {/* Simulate Email Webhook Trigger (Admin Only) */}
          {user?.role === 'ADMIN' && (
            <button
              onClick={() => setIsSimulateOpen(true)}
              className="btn btn-primary"
              style={{ fontSize: '0.8125rem', padding: '0.45rem 0.875rem' }}
            >
              <Sparkles size={14} />
              Simulate Inbound Email
            </button>
          )}

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
                  color: user?.role === 'ADMIN' ? 'var(--accent-cyan)' : user?.role === 'PACKAGING' ? 'var(--accent-blue)' : 'var(--accent-amber)',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                {user?.role === 'ADMIN' ? 'Administrator' : user?.role === 'PACKAGING' ? 'Packaging Operator' : 'Delivery Driver'}
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
