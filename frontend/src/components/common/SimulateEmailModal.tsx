import React, { useState } from 'react';
import { api } from '../../services/api';
import { Mail, Sparkles, AlertCircle, CheckCircle2, X } from 'lucide-react';

interface SimulateEmailModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const SimulateEmailModal: React.FC<SimulateEmailModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [senderEmail, setSenderEmail] = useState('enterprise.buyer@acmecorp.com');
  const [senderName, setSenderName] = useState('Sarah Connor');
  const [subject, setSubject] = useState('Urgent Order: Office Hardware Replacements');
  const [bodyPlain, setBodyPlain] = useState(
    'Hello OpsMind team,\n\nPlease ship 3x SKU-PRO-MIC to our regional office:\n100 Broadway, 14th Floor, New York, NY 10005.\n\nThank you,\nSarah Connor\nPhone: +1-212-555-0199'
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [responseResult, setResponseResult] = useState<any | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const presets = [
    {
      title: 'Standard US Order',
      sender: 'sarah.c@acme.com',
      name: 'Sarah Connor',
      subject: 'Hardware Supplies Request',
      body: 'Hi team, please deliver 2x SKU-PRO-MIC to:\n100 Broadway, 14th Floor, New York, NY 10005.\n\nBest regards,\nSarah Connor',
    },
    {
      title: 'Multilingual Spanish Order',
      sender: 'carlos.gomez@madrid.es',
      name: 'Carlos Gomez',
      subject: 'Pedido de teclados para oficina',
      body: 'Hola equipo OpsMind,\n\nPor favor enviar 2x SKU-ES-TECLADO a:\nGran Via 28, 4A, 28013 Madrid, Espana.\n\nMuchas gracias,\nCarlos Gomez',
    },
    {
      title: 'High Volume / Out of Stock',
      sender: 'bruce.wayne@waynecorp.com',
      name: 'Bruce Wayne',
      subject: 'Bulk Equipment Purchase',
      body: 'Please send 500x SKU-PRO-MIC to:\nWayne Manor, 1007 Mountain Drive, Gotham City.\n\nRegards,\nBruce Wayne',
    },
    {
      title: 'Unclear / Needs Human Review',
      sender: 'inquiry@vague.com',
      name: 'Anonymous Client',
      subject: 'Interested in buying stuff',
      body: 'Hey, I want to order some headphones. How much is shipping?',
    },
  ];

  const handleApplyPreset = (preset: (typeof presets)[0]) => {
    setSenderEmail(preset.sender);
    setSenderName(preset.name);
    setSubject(preset.subject);
    setBodyPlain(preset.body);
    setResponseResult(null);
    setErrorMessage(null);
  };

  const handleSimulate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);
    setResponseResult(null);

    try {
      const res = await api.simulateInboundEmail({
        sender_email: senderEmail,
        sender_name: senderName,
        subject,
        body_plain: bodyPlain,
      });
      setResponseResult(res);
      onSuccess();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to simulate email ingestion');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content modal-content-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid var(--border-color)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 'var(--radius-md)',
                background: 'rgba(56, 189, 248, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent-cyan)',
              }}
            >
              <Sparkles size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.125rem' }}>Simulate Inbound Email Webhook</h3>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                Test end-to-end zero-login AI extraction, entity resolution & fulfillment trigger.
              </p>
            </div>
          </div>
          <button
            className="btn btn-secondary btn-icon"
            onClick={onClose}
            style={{ borderRadius: 'var(--radius-full)' }}
          >
            <X size={18} />
          </button>
        </div>

        <div style={{ padding: '1.5rem' }}>
          {/* Preset Buttons */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label className="form-label">Test Templates & Edge Cases</label>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {presets.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleApplyPreset(p)}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '0.4rem 0.75rem' }}
                >
                  <Mail size={13} />
                  {p.title}
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleSimulate}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label">Customer Email</label>
                <input
                  type="email"
                  required
                  className="form-input"
                  value={senderEmail}
                  onChange={(e) => setSenderEmail(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Customer Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={senderName}
                  onChange={(e) => setSenderName(e.target.value)}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Email Subject</label>
              <input
                type="text"
                required
                className="form-input"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Email Body (Raw Text)</label>
              <textarea
                required
                rows={5}
                className="form-textarea mono"
                value={bodyPlain}
                onChange={(e) => setBodyPlain(e.target.value)}
                style={{ fontSize: '0.8125rem' }}
              />
            </div>

            {errorMessage && (
              <div
                style={{
                  padding: '0.875rem',
                  marginBottom: '1rem',
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  color: '#fca5a5',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.875rem',
                }}
              >
                <AlertCircle size={18} />
                {errorMessage}
              </div>
            )}

            {responseResult && (
              <div
                style={{
                  padding: '1rem',
                  marginBottom: '1rem',
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(16, 185, 129, 0.1)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '0.5rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <CheckCircle2 size={18} color="var(--accent-emerald)" />
                    <span style={{ fontWeight: 600, color: 'var(--accent-emerald)' }}>
                      Ingestion Result: {responseResult.status}
                    </span>
                  </div>
                  {responseResult.order_id && (
                    <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      Order ID: {responseResult.order_id.slice(0, 8)}...
                    </span>
                  )}
                </div>

                <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  Language: <strong style={{ color: 'var(--text-primary)' }}>{responseResult.detected_language}</strong> |
                  Confidence: <strong style={{ color: 'var(--text-primary)' }}>{(responseResult.ai_confidence * 100).toFixed(0)}%</strong>
                  {responseResult.needs_human_review && (
                    <span style={{ color: 'var(--accent-amber)', marginLeft: '0.5rem' }}>
                      (Routed to Human Review Queue)
                    </span>
                  )}
                </div>

                {responseResult.review_reasons?.length > 0 && (
                  <ul style={{ marginTop: '0.5rem', paddingLeft: '1.25rem', color: '#fca5a5', fontSize: '0.8125rem' }}>
                    {responseResult.review_reasons.map((r: string, idx: number) => (
                      <li key={idx}>{r}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button type="button" className="btn btn-secondary" onClick={onClose}>
                Close
              </button>
              <button type="submit" disabled={isSubmitting} className="btn btn-primary">
                {isSubmitting ? 'Processing AI Pipeline...' : 'Simulate Inbound Webhook'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
