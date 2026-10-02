import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { StatusBadge } from '../common/StatusBadge';
import {
  CheckCircle2,
  RefreshCw,
  ShieldAlert,
  Trash2,
} from 'lucide-react';
import type { Order } from '../../types';

export const ReviewQueueView: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [reasonNotes, setReasonNotes] = useState<string>('');
  const [isResolving, setIsResolving] = useState(false);

  const fetchReviewOrders = async () => {
    setLoading(true);
    try {
      const [reviewRes, stockRes] = await Promise.all([
        api.getOrders({ status: 'NEEDS_REVIEW', page_size: 50 }),
        api.getOrders({ status: 'OUT_OF_STOCK', page_size: 50 }),
      ]);
      const combined = [...(reviewRes.data || []), ...(stockRes.data || [])];
      setOrders(combined);
      if (combined.length > 0) {
        if (!selectedOrder || !combined.some((o) => o.id === selectedOrder.id)) {
          setSelectedOrder(combined[0]);
        }
      } else {
        setSelectedOrder(null);
      }
    } catch (err) {
      console.error('Failed to load review queue:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReviewOrders();
  }, []);

  const handleQuickDismiss = async (orderId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setIsResolving(true);
    try {
      await api.updateOrderStatus(orderId, 'CANCELLED', 'Dismissed by administrator (Non-order / Spam / Marketing email)');
      if (selectedOrder?.id === orderId) {
        setSelectedOrder(null);
      }
      await fetchReviewOrders();
    } catch (err: any) {
      alert(`Dismiss failed: ${err.message}`);
    } finally {
      setIsResolving(false);
    }
  };

  const handleApproveOrder = async () => {
    if (!selectedOrder) return;
    setIsResolving(true);
    try {
      await api.updateOrderStatus(
        selectedOrder.id,
        'CONFIRMED',
        reasonNotes.trim() || 'Approved & stock reserved by administrator'
      );
      setSelectedOrder(null);
      setReasonNotes('');
      await fetchReviewOrders();
    } catch (err: any) {
      alert(`Approval failed: ${err.message}`);
    } finally {
      setIsResolving(false);
    }
  };

  const handleRejectOrder = async () => {
    if (!selectedOrder) return;
    setIsResolving(true);
    try {
      await api.updateOrderStatus(
        selectedOrder.id,
        'CANCELLED',
        reasonNotes.trim() || 'Rejected & cancelled by administrator'
      );
      setSelectedOrder(null);
      setReasonNotes('');
      await fetchReviewOrders();
    } catch (err: any) {
      alert(`Rejection failed: ${err.message}`);
    } finally {
      setIsResolving(false);
    }
  };


  return (
    <div className="page-wrapper">
      {/* Header */}
      <div className="responsive-header" style={{ marginBottom: '1.5rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', flexWrap: 'wrap' }}>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>AI Exception & Review Queue</h1>
            <span
              style={{
                background: 'rgba(239, 68, 68, 0.15)',
                color: '#f87171',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                padding: '0.2rem 0.6rem',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.75rem',
                fontWeight: 700,
              }}
            >
              {orders.length} Pending
            </span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Human-in-the-loop triage for ambiguous catalog matches, missing address fields, or inventory stockouts.
          </p>
        </div>

        <button onClick={fetchReviewOrders} disabled={loading} className="btn btn-secondary">
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Queue</span>
        </button>
      </div>

      {orders.length === 0 ? (
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
          <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>Review Queue is Clear!</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', maxWidth: 450, margin: '0 auto' }}>
            All incoming emails were parsed above safety confidence thresholds and dispatched autonomously.
          </p>
        </div>
      ) : (
        <div className="portal-split-layout">
          {/* Left Column: List of Flagged Orders */}
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
              Flagged Inbound Orders
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {orders.map((o) => {
                const isSelected = selectedOrder?.id === o.id;
                return (
                  <div
                    key={o.id}
                    onClick={() => setSelectedOrder(o)}
                    style={{
                      padding: '0.875rem',
                      borderRadius: 'var(--radius-md)',
                      background: isSelected ? 'rgba(56, 189, 248, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                      border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      position: 'relative',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                      <span className="mono" style={{ fontWeight: 600, fontSize: '0.8125rem' }}>
                        {o.order_number}
                      </span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                        <StatusBadge status={o.status} />
                        <button
                          type="button"
                          title="Quick Dismiss / Delete from Queue"
                          onClick={(e) => handleQuickDismiss(o.id, e)}
                          disabled={isResolving}
                          style={{
                            background: 'rgba(239, 68, 68, 0.1)',
                            border: '1px solid rgba(239, 68, 68, 0.3)',
                            color: '#f87171',
                            borderRadius: 'var(--radius-sm)',
                            padding: '0.2rem 0.4rem',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '0.75rem',
                            transition: 'all 0.15s ease',
                          }}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                    <div style={{ fontSize: '0.8125rem', fontWeight: 500 }}>{o.customer_name || 'Customer'}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {o.customer_email}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Split-View Triage Panel */}
          {selectedOrder && (
            <div className="glass-panel" style={{ padding: '1.5rem' }}>
              {/* Selected Order Header */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingBottom: '1.25rem',
                  borderBottom: '1px solid var(--border-color)',
                  marginBottom: '1.25rem',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <h3 className="mono" style={{ fontSize: '1.25rem' }}>
                      {selectedOrder.order_number}
                    </h3>
                    <StatusBadge status={selectedOrder.status} />
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    Customer: {selectedOrder.customer_name} ({selectedOrder.customer_email})
                  </div>
                </div>

                <div className="mono" style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--accent-emerald)' }}>
                  ${Number(selectedOrder.total_amount ?? 0).toFixed(2)}
                </div>
              </div>

              {/* Extraction & Guardrail Analysis */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', marginBottom: '1.5rem' }}>
                {/* Shipping & Contact info */}
                <div
                  style={{
                    padding: '1rem',
                    borderRadius: 'var(--radius-md)',
                    background: 'rgba(0, 0, 0, 0.25)',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
                    Delivery Target
                  </div>
                  <p style={{ fontSize: '0.875rem' }}>{selectedOrder.shipping_address || 'No shipping address extracted'}</p>
                </div>

                {/* Stock or Ambiguity Warning */}
                <div
                  style={{
                    padding: '1rem',
                    borderRadius: 'var(--radius-md)',
                    background: selectedOrder.status === 'OUT_OF_STOCK' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(234, 179, 8, 0.1)',
                    border: selectedOrder.status === 'OUT_OF_STOCK' ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid rgba(234, 179, 8, 0.3)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                    <ShieldAlert size={16} color={selectedOrder.status === 'OUT_OF_STOCK' ? '#f87171' : '#facc15'} />
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: selectedOrder.status === 'OUT_OF_STOCK' ? '#f87171' : '#facc15' }}>
                      {selectedOrder.status === 'OUT_OF_STOCK' ? 'Stock Depletion Warning' : 'Parsing Validation Flag'}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    {selectedOrder.status === 'OUT_OF_STOCK'
                      ? 'The requested quantity exceeded available stock. Adjust stock in Inventory or reject the order.'
                      : 'Address or product match fell below autonomous threshold. Review and confirm.'}
                  </p>
                </div>
              </div>

              {/* Line Items in Flagged Order */}
              <div style={{ marginBottom: '1.5rem' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.75rem' }}>
                  Extracted Line Items
                </div>
                {(!selectedOrder.items || selectedOrder.items.length === 0) ? (
                  <div style={{ padding: '0.875rem', borderRadius: 'var(--radius-md)', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
                    No valid order line items extracted (Likely a newsletter / spam / non-order email).
                  </div>
                ) : (
                  selectedOrder.items.map((item) => (
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
                        marginBottom: '0.5rem',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 600 }}>{item.product_name}</div>
                        <div className="mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                          SKU: {item.sku}
                        </div>
                      </div>
                      <div className="mono" style={{ fontWeight: 600 }}>
                        {item.quantity} units @ ${Number(item.unit_price ?? 0).toFixed(2)} = ${Number(item.total_price ?? 0).toFixed(2)}
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Operator Action Bar */}
              <div
                style={{
                  padding: '1.25rem',
                  borderRadius: 'var(--radius-lg)',
                  background: 'rgba(17, 24, 39, 0.8)',
                  border: '1px solid var(--border-glass)',
                }}
              >
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.75rem' }}>
                  Resolve & Decision Triage
                </div>

                <div style={{ marginBottom: '1rem' }}>
                  <label className="form-label">Audit / Resolution Notes (Optional)</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Non-order marketing email / False positive / Approved manual override"
                    value={reasonNotes}
                    onChange={(e) => setReasonNotes(e.target.value)}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={handleRejectOrder}
                    disabled={isResolving}
                    className="btn"
                    style={{
                      background: 'rgba(239, 68, 68, 0.15)',
                      color: '#f87171',
                      border: '1px solid rgba(239, 68, 68, 0.35)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      fontWeight: 600,
                    }}
                  >
                    <Trash2 size={16} />
                    <span>Reject & Dismiss (Non-Order / Spam)</span>
                  </button>

                  <button
                    type="button"
                    onClick={handleApproveOrder}
                    disabled={isResolving}
                    className="btn btn-primary"
                    style={{
                      background: 'linear-gradient(135deg, #059669 0%, #047857 100%)',
                      borderColor: 'rgba(16, 185, 129, 0.4)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      fontWeight: 600,
                    }}
                  >
                    <CheckCircle2 size={16} />
                    <span>Approve & Confirm Fulfillment</span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
