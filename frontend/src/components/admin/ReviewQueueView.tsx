import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { StatusBadge } from '../common/StatusBadge';
import {
  CheckCircle2,
  RefreshCw,
  ShieldAlert,
} from 'lucide-react';
import type { Order } from '../../types';

export const ReviewQueueView: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [resolutionAction, setResolutionAction] = useState<string>('APPROVE_CONFIRMED');
  const [reasonNotes, setReasonNotes] = useState<string>('Resolved by administrator review');
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
      if (combined.length > 0 && !selectedOrder) {
        setSelectedOrder(combined[0]);
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

  const handleResolveOrder = async () => {
    if (!selectedOrder) return;
    setIsResolving(true);
    try {
      if (resolutionAction === 'APPROVE_CONFIRMED') {
        await api.updateOrderStatus(selectedOrder.id, 'CONFIRMED', reasonNotes);
      } else if (resolutionAction === 'CANCEL') {
        await api.updateOrderStatus(selectedOrder.id, 'CANCELLED', reasonNotes);
      }
      setSelectedOrder(null);
      await fetchReviewOrders();
    } catch (err: any) {
      alert(`Resolution failed: ${err.message}`);
    } finally {
      setIsResolving(false);
    }
  };

  return (
    <div className="page-wrapper">
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '1.5rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
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
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1.5rem', alignItems: 'start' }}>
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
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                      <span className="mono" style={{ fontWeight: 600, fontSize: '0.8125rem' }}>
                        {o.order_number}
                      </span>
                      <StatusBadge status={o.status} />
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
                {selectedOrder.items?.map((item) => (
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
                ))}
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
                  Resolve & Dispatch Order
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem', marginBottom: '1rem' }}>
                  <div>
                    <label className="form-label">Triage Action</label>
                    <select
                      className="form-select"
                      value={resolutionAction}
                      onChange={(e) => setResolutionAction(e.target.value)}
                    >
                      <option value="APPROVE_CONFIRMED">Approve & Reserve Stock (CONFIRMED)</option>
                      <option value="CANCEL">Reject & Cancel Order</option>
                    </select>
                  </div>

                  <div>
                    <label className="form-label">Audit Notes</label>
                    <input
                      type="text"
                      className="form-input"
                      value={reasonNotes}
                      onChange={(e) => setReasonNotes(e.target.value)}
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                  <button
                    onClick={handleResolveOrder}
                    disabled={isResolving}
                    className="btn btn-primary"
                    style={{
                      background:
                        resolutionAction === 'CANCEL'
                          ? 'linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)'
                          : 'linear-gradient(135deg, #059669 0%, #047857 100%)',
                      borderColor:
                        resolutionAction === 'CANCEL'
                          ? 'rgba(239, 68, 68, 0.4)'
                          : 'rgba(16, 185, 129, 0.4)',
                    }}
                  >
                    {isResolving ? 'Processing...' : resolutionAction === 'CANCEL' ? 'Cancel Order' : 'Approve & Confirm Fulfillment'}
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
