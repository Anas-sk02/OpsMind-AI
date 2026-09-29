import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { StatusBadge } from '../common/StatusBadge';
import {
  ShoppingCart,
  Search,
  RefreshCw,
  MapPin,
  Mail,
  User,
  X,
  History,
} from 'lucide-react';
import type { Order } from '../../types';

interface OrdersViewProps {
  selectedOrderModal?: Order | null;
  onCloseModal?: () => void;
}

export const OrdersView: React.FC<OrdersViewProps> = ({
  selectedOrderModal,
  onCloseModal,
}) => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeModalOrder, setActiveModalOrder] = useState<Order | null>(
    selectedOrderModal || null
  );

  useEffect(() => {
    if (selectedOrderModal) {
      setActiveModalOrder(selectedOrderModal);
    }
  }, [selectedOrderModal]);

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const res = await api.getOrders({
        status: statusFilter === 'ALL' ? undefined : statusFilter,
        page_size: 50,
      });
      setOrders(res.data || []);
    } catch (err) {
      console.error('Failed to fetch orders:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [statusFilter]);

  const openOrderDetail = async (order: Order) => {
    try {
      const detailed = await api.getOrder(order.id);
      setActiveModalOrder(detailed);
    } catch {
      setActiveModalOrder(order);
    }
  };

  const filteredOrders = orders.filter((o) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      o.order_number.toLowerCase().includes(query) ||
      (o.customer_name && o.customer_name.toLowerCase().includes(query)) ||
      (o.customer_email && o.customer_email.toLowerCase().includes(query)) ||
      o.shipping_address.toLowerCase().includes(query)
    );
  });

  const statuses: { label: string; value: string }[] = [
    { label: 'All Orders', value: 'ALL' },
    { label: 'Confirmed', value: 'CONFIRMED' },
    { label: 'Packaging', value: 'PACKAGING' },
    { label: 'Packed', value: 'PACKED' },
    { label: 'Out for Delivery', value: 'OUT_FOR_DELIVERY' },
    { label: 'Delivered', value: 'DELIVERED' },
    { label: 'Needs Review', value: 'NEEDS_REVIEW' },
    { label: 'Out of Stock', value: 'OUT_OF_STOCK' },
  ];

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
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>Orders & Fulfillment Pipeline</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Track end-to-end lifecycle transitions, assigned task progression & immutable audit events.
          </p>
        </div>

        <button onClick={fetchOrders} disabled={loading} className="btn btn-secondary">
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div
        className="glass-panel"
        style={{
          padding: '1rem',
          marginBottom: '1.5rem',
          display: 'flex',
          gap: '1rem',
          alignItems: 'center',
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
            placeholder="Search by Order #, Customer, Email, Address..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: '2.25rem' }}
          />
        </div>

        {/* Status Pills */}
        <div style={{ display: 'flex', gap: '0.35rem', overflowX: 'auto', paddingBottom: '0.2rem' }}>
          {statuses.map((st) => (
            <button
              key={st.value}
              onClick={() => setStatusFilter(st.value)}
              className="btn btn-secondary"
              style={{
                fontSize: '0.75rem',
                padding: '0.4rem 0.75rem',
                background:
                  statusFilter === st.value
                    ? 'rgba(56, 189, 248, 0.15)'
                    : 'rgba(255, 255, 255, 0.03)',
                borderColor:
                  statusFilter === st.value
                    ? 'var(--accent-cyan)'
                    : 'var(--border-color)',
                color:
                  statusFilter === st.value
                    ? 'var(--accent-cyan)'
                    : 'var(--text-secondary)',
              }}
            >
              {st.label}
            </button>
          ))}
        </div>
      </div>

      {/* Orders Table */}
      <div className="table-container">
        <table className="ops-table">
          <thead>
            <tr>
              <th>Order Number</th>
              <th>Customer</th>
              <th>Status</th>
              <th>Shipping Address</th>
              <th>Items</th>
              <th>Total</th>
              <th>Date</th>
              <th>Timeline</th>
            </tr>
          </thead>
          <tbody>
            {filteredOrders.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                  No orders found matching the filter criteria.
                </td>
              </tr>
            ) : (
              filteredOrders.map((order) => (
                <tr key={order.id}>
                  <td className="mono" style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>
                    {order.order_number}
                  </td>
                  <td>
                    <div style={{ fontWeight: 500 }}>{order.customer_name || 'Anonymous Customer'}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{order.customer_email}</div>
                  </td>
                  <td>
                    <StatusBadge status={order.status} />
                  </td>
                  <td style={{ maxWidth: 220, fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {order.shipping_address}
                    </div>
                  </td>
                  <td>
                    {order.items?.length > 0 ? (
                      <span style={{ fontSize: '0.8125rem' }}>
                        {order.items.reduce((s, i) => s + i.quantity, 0)} units ({order.items.length} SKUs)
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>-</span>
                    )}
                  </td>
                  <td className="mono" style={{ fontWeight: 600 }}>
                    ${order.total_amount.toFixed(2)}
                  </td>
                  <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    {new Date(order.created_at).toLocaleDateString([], {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </td>
                  <td>
                    <button
                      onClick={() => openOrderDetail(order)}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}
                    >
                      <History size={14} />
                      <span>Timeline</span>
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Order Detail & Event Timeline Modal */}
      {activeModalOrder && (
        <div
          className="modal-overlay"
          onClick={() => {
            setActiveModalOrder(null);
            if (onCloseModal) onCloseModal();
          }}
        >
          <div
            className="modal-content modal-content-lg"
            onClick={(e) => e.stopPropagation()}
            style={{ padding: 0 }}
          >
            {/* Modal Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '1.25rem 1.5rem',
                borderBottom: '1px solid var(--border-color)',
                background: 'rgba(17, 24, 39, 0.8)',
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
                  <ShoppingCart size={18} />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <h3 className="mono" style={{ fontSize: '1.125rem' }}>
                      {activeModalOrder.order_number}
                    </h3>
                    <StatusBadge status={activeModalOrder.status} />
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Created: {new Date(activeModalOrder.created_at).toLocaleString()}
                  </div>
                </div>
              </div>

              <button
                className="btn btn-secondary btn-icon"
                onClick={() => {
                  setActiveModalOrder(null);
                  if (onCloseModal) onCloseModal();
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '1.5rem', display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1.5rem' }}>
              {/* Left Column: Customer & Items */}
              <div>
                {/* Customer Card */}
                <div
                  className="glass-panel"
                  style={{ padding: '1rem', marginBottom: '1.25rem' }}
                >
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
                    Customer Details
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <User size={14} color="var(--accent-cyan)" />
                    <span style={{ fontWeight: 600 }}>{activeModalOrder.customer_name || 'Customer'}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    <Mail size={14} />
                    <span>{activeModalOrder.customer_email}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    <MapPin size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                    <span>{activeModalOrder.shipping_address}</span>
                  </div>
                </div>

                {/* Line Items */}
                <div className="glass-panel" style={{ padding: '1rem' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.75rem' }}>
                    Purchased Line Items
                  </div>
                  {activeModalOrder.items?.map((item) => (
                    <div
                      key={item.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.5rem 0',
                        borderBottom: '1px solid var(--border-color)',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{item.product_name}</div>
                        <div className="mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                          SKU: {item.sku}
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div className="mono" style={{ fontWeight: 600 }}>
                          {item.quantity} x ${item.unit_price.toFixed(2)}
                        </div>
                        <div className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          ${item.total_price.toFixed(2)}
                        </div>
                      </div>
                    </div>
                  ))}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      paddingTop: '0.75rem',
                      fontWeight: 700,
                      fontSize: '1rem',
                    }}
                  >
                    <span>Total Amount</span>
                    <span className="mono" style={{ color: 'var(--accent-emerald)' }}>
                      ${activeModalOrder.total_amount.toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Right Column: Immutable Event Timeline */}
              <div>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.75rem' }}>
                  State Machine Audit Timeline
                </div>

                <div style={{ position: 'relative', paddingLeft: '1.25rem', borderLeft: '2px solid var(--border-color)' }}>
                  {activeModalOrder.events && activeModalOrder.events.length > 0 ? (
                    activeModalOrder.events.map((ev, idx) => (
                      <div key={ev.id || idx} style={{ marginBottom: '1.25rem', position: 'relative' }}>
                        {/* Bullet Dot */}
                        <div
                          style={{
                            position: 'absolute',
                            left: '-1.625rem',
                            top: '0.2rem',
                            width: 10,
                            height: 10,
                            borderRadius: '50%',
                            background: idx === 0 ? 'var(--accent-cyan)' : '#475569',
                            boxShadow: idx === 0 ? '0 0 8px var(--accent-cyan)' : 'none',
                          }}
                        />
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ fontWeight: 600, fontSize: '0.8125rem' }}>{ev.event_type}</span>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                            {new Date(ev.created_at).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit',
                            })}
                          </span>
                        </div>
                        {ev.to_status && (
                          <div style={{ marginTop: '0.25rem' }}>
                            <StatusBadge status={ev.to_status} />
                          </div>
                        )}
                        {ev.description && (
                          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
                            {ev.description}
                          </p>
                        )}
                      </div>
                    ))
                  ) : (
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                      No events logged yet for this order.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
