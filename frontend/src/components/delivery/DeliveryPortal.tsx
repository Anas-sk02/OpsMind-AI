import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { StatusBadge } from '../common/StatusBadge';
import {
  Truck,
  Phone,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Navigation,
  CheckCheck,
  X,
} from 'lucide-react';
import type { Task } from '../../types';

export const DeliveryPortal: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Delivery confirmation modal
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [recipientNote, setRecipientNote] = useState('Handed directly to recipient at front door.');

  // Exception modal
  const [isExceptionOpen, setIsExceptionOpen] = useState(false);
  const [exceptionReason, setExceptionReason] = useState('Customer unavailable at delivery address.');

  const fetchMyTasks = async () => {
    setIsRefreshing(true);
    try {
      const myTasks = await api.getMyTasks();
      const deliveryTasks = (myTasks || []).filter((t) => t.task_type === 'DELIVERY' && t.status !== 'COMPLETED');
      setTasks(deliveryTasks);
      if (deliveryTasks.length > 0 && (!activeTask || !deliveryTasks.find((t) => t.id === activeTask.id))) {
        setActiveTask(deliveryTasks[0]);
      } else if (deliveryTasks.length === 0) {
        setActiveTask(null);
      }
    } catch (err) {
      console.error('Failed to load delivery tasks:', err);
    } finally {
      setTimeout(() => {
        setIsRefreshing(false);
      }, 350);
    }
  };

  useEffect(() => {
    fetchMyTasks();
  }, []);

  const handleStartDelivery = async () => {
    if (!activeTask) return;
    setIsSubmitting(true);
    try {
      await api.startTask(activeTask.id);
      await fetchMyTasks();
    } catch (err: any) {
      alert(`Failed to start delivery: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmDelivered = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTask) return;
    setIsSubmitting(true);
    try {
      await api.completeTask(activeTask.id, {
        notes: recipientNote,
      });
      setIsConfirmOpen(false);
      await fetchMyTasks();
    } catch (err: any) {
      alert(`Delivery confirmation failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReportException = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTask) return;
    setIsSubmitting(true);
    try {
      await api.reportTaskException(activeTask.id, exceptionReason);
      setIsExceptionOpen(false);
      await fetchMyTasks();
    } catch (err: any) {
      alert(`Failed delivery report failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const openMapsUrl = (address: string) => {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`;
  };

  return (
    <div className="page-wrapper" style={{ maxWidth: 1080 }}>
      {/* Header */}
      <div className="responsive-header" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 'var(--radius-md)',
              background: 'rgba(245, 158, 11, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-amber)',
            }}
          >
            <Truck size={24} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Driver Route & Delivery Terminal</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
              One-touch navigation, customer dialing & idempotent delivery sign-off.
            </p>
          </div>
        </div>

        <button onClick={fetchMyTasks} disabled={isRefreshing} className="btn btn-secondary">
          <RefreshCw size={15} className={isRefreshing ? 'animate-spin' : ''} />
          <span>{isRefreshing ? 'Refreshing...' : 'Refresh Route'}</span>
        </button>
      </div>

      {tasks.length === 0 ? (
        <div
          className="glass-panel"
          style={{
            padding: '4rem 2rem',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: '50%',
              background: 'rgba(16, 185, 129, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-emerald)',
              margin: '0 auto 1rem',
            }}
          >
            <CheckCircle2 size={28} />
          </div>
          <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>Route Completed!</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            No pending deliveries on your route right now. You will receive assignments when orders are packed.
          </p>
        </div>
      ) : (
        <div className="portal-split-layout">
          {/* Left Column: Route List */}
          <div className="glass-panel" style={{ padding: '0.75rem', maxHeight: '75vh', overflowY: 'auto' }}>
            <div
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                color: 'var(--text-muted)',
                textTransform: 'uppercase',
                padding: '0.5rem',
              }}
            >
              Today's Delivery Stops ({tasks.length})
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {tasks.map((task, idx) => {
                const isSelected = activeTask?.id === task.id;
                return (
                  <div
                    key={task.id}
                    onClick={() => setActiveTask(task)}
                    style={{
                      padding: '1rem',
                      borderRadius: 'var(--radius-md)',
                      background: isSelected ? 'rgba(245, 158, 11, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                      border: isSelected ? '1px solid var(--accent-amber)' : '1px solid var(--border-color)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                      <span className="mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>
                        #{idx + 1} — {task.order_number || task.order?.order_number || `Order ${task.order_id.slice(0, 8)}`}
                      </span>
                      <StatusBadge status={task.order_status || task.order?.status || 'PACKED'} />
                    </div>

                    <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {task.customer_name || task.order?.customer_name || 'Customer'}
                    </div>

                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {task.delivery_address || task.order?.shipping_address}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Execution Card */}
          {activeTask && (
            <div className="glass-panel" style={{ padding: '1.75rem' }}>
              {/* Stop Header */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingBottom: '1.25rem',
                  borderBottom: '1px solid var(--border-color)',
                  marginBottom: '1.5rem',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <h2 className="mono" style={{ fontSize: '1.375rem' }}>
                      {activeTask.order_number || activeTask.order?.order_number || `Order ${activeTask.order_id.slice(0, 8)}`}
                    </h2>
                    <StatusBadge status={activeTask.order_status || activeTask.order?.status || 'PACKED'} />
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                    Task ID: {activeTask.id}
                  </div>
                </div>

                <button
                  onClick={() => setIsExceptionOpen(true)}
                  className="btn btn-danger"
                  style={{ fontSize: '0.8125rem' }}
                >
                  <AlertTriangle size={15} />
                  <span>Delivery Failed</span>
                </button>
              </div>

              {/* Customer & Address Touch Actions */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                {/* Customer Call Card */}
                <div
                  className="glass-panel"
                  style={{
                    padding: '1.25rem',
                    background: 'rgba(0, 0, 0, 0.25)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.35rem' }}>
                      Customer Contact
                    </div>
                    <div style={{ fontSize: '1.125rem', fontWeight: 600 }}>
                      {activeTask.customer_name || activeTask.order?.customer_name || 'Customer'}
                    </div>
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                      {activeTask.customer_email || activeTask.order?.customer_email}
                    </div>
                  </div>

                  {(activeTask.order?.customer_phone || (activeTask as any).customer_phone) && (
                    <a
                      href={`tel:${activeTask.order?.customer_phone || (activeTask as any).customer_phone}`}
                      className="btn btn-secondary"
                      style={{ marginTop: '1rem', color: 'var(--accent-cyan)' }}
                    >
                      <Phone size={15} />
                      <span>Call {activeTask.order?.customer_phone || (activeTask as any).customer_phone}</span>
                    </a>
                  )}
                </div>

                {/* Navigation Card */}
                <div
                  className="glass-panel"
                  style={{
                    padding: '1.25rem',
                    background: 'rgba(0, 0, 0, 0.25)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.35rem' }}>
                      Destination Address
                    </div>
                    <p style={{ fontSize: '0.9375rem', lineHeight: 1.4, color: 'var(--text-primary)' }}>
                      {activeTask.delivery_address || activeTask.order?.shipping_address || 'Delivery Address'}
                    </p>
                  </div>

                  <a
                    href={openMapsUrl(activeTask.delivery_address || activeTask.order?.shipping_address || '')}
                    target="_blank"
                    rel="noreferrer"
                    className="btn btn-secondary"
                    style={{ marginTop: '1rem', color: 'var(--accent-amber)' }}
                  >
                    <Navigation size={15} />
                    <span>Open in Google Maps</span>
                    <ExternalLink size={13} />
                  </a>
                </div>
              </div>

              {/* Items Summary in Package */}
              <div style={{ marginBottom: '2rem' }}>
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.75rem' }}>
                  Package Contents ({(activeTask.items || activeTask.order?.items)?.length || 0} items)
                </div>
                {(activeTask.items || activeTask.order?.items)?.map((item) => (
                  <div
                    key={item.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.75rem 1rem',
                      borderRadius: 'var(--radius-md)',
                      background: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid var(--border-color)',
                      marginBottom: '0.35rem',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600 }}>{item.product_name}</div>
                      <div className="mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                        SKU: {item.product_sku || (item as any).sku}
                      </div>
                    </div>
                    <div className="mono" style={{ fontWeight: 700 }}>
                      QTY: {item.quantity}
                    </div>
                  </div>
                ))}
              </div>

              {/* Step-by-Step Delivery Action Progression */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                {(activeTask.order_status === 'OUT_FOR_DELIVERY' ||
                  activeTask.order?.status === 'OUT_FOR_DELIVERY' ||
                  activeTask.status === 'IN_PROGRESS') ? (
                  <button
                    onClick={() => setIsConfirmOpen(true)}
                    disabled={isSubmitting}
                    className="btn btn-success"
                    style={{
                      padding: '1rem',
                      fontSize: '1rem',
                      fontWeight: 700,
                      gridColumn: 'span 2',
                      boxShadow: '0 0 20px rgba(16, 185, 129, 0.3)',
                    }}
                  >
                    <CheckCheck size={20} />
                    <span>CONFIRM DELIVERY (MARK AS DELIVERED)</span>
                  </button>
                ) : (
                  <button
                    onClick={handleStartDelivery}
                    disabled={isSubmitting}
                    className="btn btn-primary"
                    style={{
                      padding: '1rem',
                      fontSize: '1rem',
                      fontWeight: 700,
                      gridColumn: 'span 2',
                      background: 'linear-gradient(135deg, #d97706 0%, #b45309 100%)',
                      borderColor: 'rgba(245, 158, 11, 0.4)',
                    }}
                  >
                    <Truck size={20} />
                    <span>START DELIVERY ROUTE (OUT FOR DELIVERY)</span>
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Confirm Delivery Modal */}
      {isConfirmOpen && (
        <div className="modal-overlay" onClick={() => setIsConfirmOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '1.25rem 1.5rem',
                borderBottom: '1px solid var(--border-color)',
              }}
            >
              <h3 style={{ fontSize: '1.125rem', color: 'var(--accent-emerald)' }}>
                Confirm Successful Delivery
              </h3>
              <button className="btn btn-secondary btn-icon" onClick={() => setIsConfirmOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleConfirmDelivered} style={{ padding: '1.5rem' }}>
              <div className="form-group">
                <label className="form-label">Delivery Note / Proof of Delivery</label>
                <textarea
                  required
                  rows={3}
                  className="form-textarea"
                  value={recipientNote}
                  onChange={(e) => setRecipientNote(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsConfirmOpen(false)}>
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="btn btn-success">
                  {isSubmitting ? 'Confirming...' : 'Mark Delivered & Complete Task'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delivery Exception Modal */}
      {isExceptionOpen && (
        <div className="modal-overlay" onClick={() => setIsExceptionOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '1.25rem 1.5rem',
                borderBottom: '1px solid var(--border-color)',
              }}
            >
              <h3 style={{ fontSize: '1.125rem', color: '#f87171' }}>Report Delivery Exception</h3>
              <button className="btn btn-secondary btn-icon" onClick={() => setIsExceptionOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleReportException} style={{ padding: '1.5rem' }}>
              <div className="form-group">
                <label className="form-label">Exception Reason</label>
                <textarea
                  required
                  rows={3}
                  className="form-textarea"
                  value={exceptionReason}
                  onChange={(e) => setExceptionReason(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsExceptionOpen(false)}>
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="btn btn-danger">
                  {isSubmitting ? 'Submitting...' : 'Record Failed Delivery'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
