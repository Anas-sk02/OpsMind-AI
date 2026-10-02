import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import {
  Mail,
  ArrowDownLeft,
  ArrowUpRight,
  Globe,
  RefreshCw,
  Search,
  Eye,
  X,
  Sparkles,
} from 'lucide-react';
import type { EmailMessage } from '../../types';

export const EmailAuditView: React.FC = () => {
  const [emails, setEmails] = useState<EmailMessage[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [directionFilter, setDirectionFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEmail, setSelectedEmail] = useState<EmailMessage | null>(null);
  const [pollingMailbox, setPollingMailbox] = useState(false);
  const [pollMessage, setPollMessage] = useState<string | null>(null);

  const fetchEmails = async () => {
    setIsRefreshing(true);
    try {
      const res = await api.getEmailMessages({
        direction: directionFilter === 'ALL' ? undefined : directionFilter,
        search: searchQuery || undefined,
        page_size: 100,
      });
      setEmails(res.data || []);
    } catch (err) {
      console.error('Failed to load email messages:', err);
    } finally {
      setTimeout(() => {
        setIsRefreshing(false);
      }, 350);
    }
  };

  const handlePollMailbox = async () => {
    setPollingMailbox(true);
    setPollMessage(null);
    try {
      const res = await api.pollMailboxNow();
      setPollMessage(res.message || `Mailbox checked: ${res.count} new emails.`);
      await fetchEmails();
      setTimeout(() => setPollMessage(null), 5000);
    } catch (err: any) {
      setPollMessage(err.message || 'Failed to poll mailbox. Check credentials.');
      setTimeout(() => setPollMessage(null), 5000);
    } finally {
      setPollingMailbox(false);
    }
  };

  useEffect(() => {
    fetchEmails();
  }, [directionFilter]);

  const filteredEmails = emails.filter((em) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      em.sender_email.toLowerCase().includes(q) ||
      em.recipient_email.toLowerCase().includes(q) ||
      em.subject.toLowerCase().includes(q) ||
      em.body_plain.toLowerCase().includes(q)
    );
  });

  return (
    <div className="page-wrapper">
      {/* Header */}
      <div className="responsive-header" style={{ marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>Inbound & Outbound Email Stream</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Zero-login communication audit logs, multilingual NLP detection & fact-grounded response synthesis.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            onClick={handlePollMailbox}
            disabled={pollingMailbox}
            className="btn btn-primary"
            style={{ padding: '0.45rem 0.9rem' }}
          >
            <Mail size={15} className={pollingMailbox ? 'animate-spin' : ''} />
            <span>{pollingMailbox ? 'Checking Inbox...' : 'Check Mailbox Now'}</span>
          </button>
          <button onClick={fetchEmails} disabled={isRefreshing} className="btn btn-secondary">
            <RefreshCw size={15} className={isRefreshing ? 'animate-spin' : ''} />
            <span>{isRefreshing ? 'Refreshing...' : 'Refresh Stream'}</span>
          </button>
        </div>
      </div>

      {pollMessage && (
        <div
          className="glass-panel"
          style={{
            padding: '0.75rem 1rem',
            marginBottom: '1rem',
            background: 'rgba(56, 189, 248, 0.1)',
            borderColor: 'var(--accent-cyan)',
            color: 'var(--accent-cyan)',
            fontSize: '0.875rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}
        >
          <Sparkles size={16} />
          <span>{pollMessage}</span>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div
        className="glass-panel"
        style={{
          padding: '1rem',
          marginBottom: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ flex: 1, minWidth: 260, position: 'relative' }}>
          <Search
            size={16}
            style={{
              position: 'absolute',
              left: '0.75rem',
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--text-muted)',
            }}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Search email sender, subject, or content..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: '2.25rem' }}
          />
        </div>

        <div style={{ display: 'flex', gap: '0.35rem' }}>
          {(['ALL', 'INBOUND', 'OUTBOUND'] as const).map((dir) => (
            <button
              key={dir}
              onClick={() => setDirectionFilter(dir)}
              className="btn btn-secondary"
              style={{
                fontSize: '0.75rem',
                padding: '0.4rem 0.75rem',
                background:
                  directionFilter === dir
                    ? 'rgba(56, 189, 248, 0.15)'
                    : 'rgba(255, 255, 255, 0.03)',
                borderColor:
                  directionFilter === dir
                    ? 'var(--accent-cyan)'
                    : 'var(--border-color)',
                color:
                  directionFilter === dir
                    ? 'var(--accent-cyan)'
                    : 'var(--text-secondary)',
              }}
            >
              {dir === 'ALL' && 'All Traffic'}
              {dir === 'INBOUND' && 'Inbound Ingested'}
              {dir === 'OUTBOUND' && 'Outbound Notified'}
            </button>
          ))}
        </div>
      </div>

      {/* Emails Table */}
      <div className="table-container">
        <table className="ops-table">
          <thead>
            <tr>
              <th>Direction</th>
              <th>Language</th>
              <th>Subject</th>
              <th>Sender</th>
              <th>Recipient</th>
              <th>Linked Order</th>
              <th>Timestamp</th>
              <th>Payload</th>
            </tr>
          </thead>
          <tbody>
            {filteredEmails.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                  No email transactions found matching the filter.
                </td>
              </tr>
            ) : (
              filteredEmails.map((em) => (
                <tr key={em.id}>
                  <td>
                    <span
                      className="badge"
                      style={{
                        background:
                          em.direction === 'INBOUND'
                            ? 'rgba(56, 189, 248, 0.15)'
                            : 'rgba(168, 85, 247, 0.15)',
                        color:
                          em.direction === 'INBOUND'
                            ? 'var(--accent-cyan)'
                            : 'var(--accent-purple)',
                        borderColor:
                          em.direction === 'INBOUND'
                            ? 'rgba(56, 189, 248, 0.3)'
                            : 'rgba(168, 85, 247, 0.3)',
                      }}
                    >
                      {em.direction === 'INBOUND' ? (
                        <ArrowDownLeft size={12} />
                      ) : (
                        <ArrowUpRight size={12} />
                      )}
                      {em.direction}
                    </span>
                  </td>
                  <td>
                    <span
                      className="badge mono"
                      style={{
                        background: 'rgba(255, 255, 255, 0.05)',
                        color: 'var(--text-secondary)',
                        textTransform: 'uppercase',
                      }}
                    >
                      <Globe size={11} />
                      {em.detected_language}
                    </span>
                  </td>
                  <td style={{ fontWeight: 600, maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {em.subject}
                  </td>
                  <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{em.sender_email}</td>
                  <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{em.recipient_email}</td>
                  <td className="mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                    {em.order_id ? `${em.order_id.slice(0, 8)}...` : '-'}
                  </td>
                  <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    {new Date(em.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td>
                    <button
                      onClick={() => setSelectedEmail(em)}
                      className="btn btn-secondary btn-icon"
                      style={{ padding: '0.35rem 0.6rem' }}
                      title="Inspect Email Body & AI Extraction"
                    >
                      <Eye size={14} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Email Detail / AI Payload Modal */}
      {selectedEmail && (
        <div className="modal-overlay" onClick={() => setSelectedEmail(null)}>
          <div className="modal-content modal-content-lg" onClick={(e) => e.stopPropagation()}>
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
                  <Mail size={18} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.125rem' }}>{selectedEmail.subject}</h3>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    From: {selectedEmail.sender_email} | To: {selectedEmail.recipient_email}
                  </div>
                </div>
              </div>

              <button className="btn btn-secondary btn-icon" onClick={() => setSelectedEmail(null)}>
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: '1.5rem', display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1.5rem' }}>
              {/* Left Column: Email Body */}
              <div>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
                  Email Body (Plaintext)
                </div>
                <div
                  className="mono"
                  style={{
                    padding: '1rem',
                    borderRadius: 'var(--radius-md)',
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid var(--border-color)',
                    fontSize: '0.8125rem',
                    lineHeight: 1.6,
                    whiteSpace: 'pre-wrap',
                    maxHeight: 350,
                    overflowY: 'auto',
                  }}
                >
                  {selectedEmail.body_plain}
                </div>
              </div>

              {/* Right Column: AI Extraction JSON */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                  <Sparkles size={14} color="var(--accent-cyan)" />
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                    AI Extraction Payload
                  </span>
                </div>

                <div
                  className="mono"
                  style={{
                    padding: '1rem',
                    borderRadius: 'var(--radius-md)',
                    background: '#090d16',
                    border: '1px solid var(--border-color)',
                    fontSize: '0.75rem',
                    color: '#38bdf8',
                    maxHeight: 350,
                    overflowY: 'auto',
                  }}
                >
                  <pre>{JSON.stringify(selectedEmail.ai_extraction_payload || { note: 'No AI payload attached (Outbound or Direct)' }, null, 2)}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
