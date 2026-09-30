import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Zap, ArrowRight, AlertCircle, Lock, Eye, EyeOff } from 'lucide-react';

export const LoginView: React.FC = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  
  // Specific error messages
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const validateInputs = (): boolean => {
    let isValid = true;
    setEmailError(null);
    setPasswordError(null);
    setGlobalError(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setEmailError('Work email address is required.');
      isValid = false;
    } else {
      // RFC-compliant email regex pattern
      const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
      if (!emailRegex.test(trimmedEmail)) {
        setEmailError('Please enter a valid work email format (e.g. name@company.com).');
        isValid = false;
      }
    }

    if (!password) {
      setPasswordError('Password is required.');
      isValid = false;
    } else if (password.length < 6) {
      setPasswordError('Password must be at least 6 characters long.');
      isValid = false;
    }

    return isValid;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateInputs()) {
      return;
    }

    setLoading(true);
    setGlobalError(null);

    try {
      await login(email.trim(), password);
    } catch (err: any) {
      const msg = err.message || '';
      
      if (msg.toLowerCase().includes('password') || msg.toLowerCase().includes('credential') || msg.toLowerCase().includes('401')) {
        setGlobalError('Incorrect email or password. Please verify your credentials and try again.');
      } else if (msg.toLowerCase().includes('deactivated')) {
        setGlobalError('This account is deactivated. Please reach out to the system administrator.');
      } else if (msg.toLowerCase().includes('connect') || msg.toLowerCase().includes('network')) {
        setGlobalError('Unable to connect to OpsMind server. Please check your internet connection or server status.');
      } else {
        setGlobalError(msg || 'Authentication failed. Please verify your details.');
      }
    } finally {
      setLoading(false);
    }
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

        {globalError && (
          <div
            role="alert"
            style={{
              padding: '0.875rem 1rem',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              color: '#fca5a5',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.625rem',
              fontSize: '0.8125rem',
              lineHeight: 1.4,
              marginBottom: '1.5rem',
            }}
          >
            <AlertCircle size={18} style={{ flexShrink: 0, marginTop: '0.1rem' }} />
            <div>
              <div style={{ fontWeight: 600, color: '#fee2e2' }}>Login Failed</div>
              <div style={{ marginTop: '0.15rem' }}>{globalError}</div>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
            <label className="form-label" htmlFor="work-email" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Work Email</span>
              {emailError && <span style={{ color: '#f87171', fontSize: '0.75rem', fontWeight: 500 }}>{emailError}</span>}
            </label>
            <input
              id="work-email"
              type="email"
              autoComplete="email"
              className="form-input"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (emailError) setEmailError(null);
                if (globalError) setGlobalError(null);
              }}
              placeholder="name@opsmind.io"
              style={{
                borderColor: emailError ? '#ef4444' : undefined,
                background: emailError ? 'rgba(239, 68, 68, 0.05)' : undefined,
              }}
            />
          </div>

          <div className="form-group" style={{ marginBottom: '1.5rem' }}>
            <label className="form-label" htmlFor="password" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Password</span>
              {passwordError && <span style={{ color: '#f87171', fontSize: '0.75rem', fontWeight: 500 }}>{passwordError}</span>}
            </label>
            <div style={{ position: 'relative' }}>
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                className="form-input"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (passwordError) setPasswordError(null);
                  if (globalError) setGlobalError(null);
                }}
                placeholder="••••••••"
                style={{
                  borderColor: passwordError ? '#ef4444' : undefined,
                  background: passwordError ? 'rgba(239, 68, 68, 0.05)' : undefined,
                  paddingRight: '2.5rem',
                }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
                style={{
                  position: 'absolute',
                  right: '0.75rem',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  padding: 0,
                }}
                title={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary"
            style={{ width: '100%', padding: '0.85rem', fontWeight: 600, letterSpacing: '0.02em' }}
          >
            {loading ? 'Authenticating...' : 'Sign In to Workspace'}
            {!loading && <ArrowRight size={16} />}
          </button>
        </form>

        {/* Secure Workspace Notice */}
        <div style={{ marginTop: '2rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border-color)', textAlign: 'center' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            <Lock size={12} />
            <span>Authorized Personnel Access Only • RBAC Protected</span>
          </div>
        </div>
      </div>
    </div>
  );
};
