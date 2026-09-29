import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Zap, ShieldCheck, Box, Truck, ArrowRight, AlertCircle } from 'lucide-react';
import type { UserRole } from '../../types';

export const LoginView: React.FC = () => {
  const { login, quickSwitchRole } = useAuth();
  const [email, setEmail] = useState('admin@opsmind.io');
  const [password, setPassword] = useState('Admin@123456!');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickRole = (role: UserRole) => {
    quickSwitchRole(role);
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.5rem',
        background: 'radial-gradient(ellipse at top, #111b2e 0%, #0b0f19 100%)',
      }}
    >
      <div
        className="glass-panel"
        style={{
          width: '100%',
          maxWidth: 440,
          padding: '2.5rem',
          boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.7)',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: 'var(--radius-lg)',
              background: 'linear-gradient(135deg, #0284c7 0%, #818cf8 100%)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              marginBottom: '1rem',
              boxShadow: '0 0 20px rgba(56, 189, 248, 0.4)',
            }}
          >
            <Zap size={28} />
          </div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>OpsMind AI</h2>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Autonomous Email-to-Delivery Fulfillment Platform
          </p>
        </div>

        {error && (
          <div
            style={{
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#fca5a5',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '0.8125rem',
              marginBottom: '1.25rem',
            }}
          >
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Work Email</label>
            <input
              type="email"
              required
              className="form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="operator@opsmind.io"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              type="password"
              required
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary"
            style={{ width: '100%', padding: '0.75rem', marginTop: '0.5rem' }}
          >
            {loading ? 'Authenticating...' : 'Sign In to Workspace'}
            {!loading && <ArrowRight size={16} />}
          </button>
        </form>

        {/* Quick Demo Access Badges */}
        <div style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-color)' }}>
          <div
            style={{
              fontSize: '0.75rem',
              color: 'var(--text-muted)',
              textAlign: 'center',
              marginBottom: '0.75rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            Quick 1-Click Role Login
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
            <button
              onClick={() => handleQuickRole('ADMIN')}
              type="button"
              className="btn btn-secondary"
              style={{ padding: '0.5rem 0.25rem', fontSize: '0.75rem', flexDirection: 'column', gap: '0.25rem' }}
            >
              <ShieldCheck size={16} color="var(--accent-cyan)" />
              <span>Admin</span>
            </button>

            <button
              onClick={() => handleQuickRole('PACKAGING')}
              type="button"
              className="btn btn-secondary"
              style={{ padding: '0.5rem 0.25rem', fontSize: '0.75rem', flexDirection: 'column', gap: '0.25rem' }}
            >
              <Box size={16} color="var(--accent-blue)" />
              <span>Packager</span>
            </button>

            <button
              onClick={() => handleQuickRole('DELIVERY')}
              type="button"
              className="btn btn-secondary"
              style={{ padding: '0.5rem 0.25rem', fontSize: '0.75rem', flexDirection: 'column', gap: '0.25rem' }}
            >
              <Truck size={16} color="var(--accent-amber)" />
              <span>Driver</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
