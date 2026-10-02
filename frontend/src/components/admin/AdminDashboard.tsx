import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { StatusBadge } from '../common/StatusBadge';
import {
  ShoppingCart,
  Box,
  Truck,
  AlertTriangle,
  Boxes,
  DollarSign,
  ArrowUpRight,
  Sparkles,
  RefreshCw,
  Clock,
  Eye,
} from 'lucide-react';
import type { DashboardMetrics, Order } from '../../types';

interface AdminDashboardProps {
  onNavigateTab: (tab: any) => void;
  onViewOrder: (order: Order) => void;
}

export const AdminDashboard: React.FC<AdminDashboardProps> = ({
  onNavigateTab,
  onViewOrder,
}) => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [recentOrders, setRecentOrders] = useState<Order[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchData = async () => {
    setIsRefreshing(true);
    try {
      const [metricsData, ordersData] = await Promise.all([
        api.getDashboardMetrics(),
        api.getOrders({ page_size: 8 }),
      ]);
      setMetrics(metricsData);
      setRecentOrders(ordersData.data || []);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    } finally {
      setTimeout(() => {
        setIsRefreshing(false);
      }, 350);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const metricCards = [
    {
      title: 'Active Orders',
      value: metrics?.active_orders ?? 0,
      icon: ShoppingCart,
      color: 'var(--accent-cyan)',
      bg: 'rgba(56, 189, 248, 0.1)',
      onClick: () => onNavigateTab('orders'),
    },
    {
      title: 'Packaging Queue',
      value: metrics?.pending_packaging ?? 0,
      icon: Box,
      color: 'var(--accent-blue)',
      bg: 'rgba(59, 130, 246, 0.1)',
      onClick: () => onNavigateTab('orders'),
    },
    {
      title: 'Out for Delivery',
      value: metrics?.out_for_delivery ?? 0,
      icon: Truck,
      color: 'var(--accent-amber)',
      bg: 'rgba(245, 158, 11, 0.1)',
      onClick: () => onNavigateTab('orders'),
    },
    {
      title: 'Needs Human Review',
      value: metrics?.needs_review_count ?? 0,
      icon: AlertTriangle,
      color: 'var(--accent-rose)',
      bg: 'rgba(239, 68, 68, 0.1)',
      highlight: (metrics?.needs_review_count ?? 0) > 0,
      onClick: () => onNavigateTab('review_queue'),
    },
    {
      title: 'Low Stock Alerts',
      value: metrics?.low_stock_count ?? 0,
      icon: Boxes,
      color: 'var(--accent-violet)',
      bg: 'rgba(129, 140, 248, 0.1)',
      onClick: () => onNavigateTab('inventory'),
    },
    {
      title: 'Total Order Volume',
      value: `$${(metrics?.total_revenue ?? 0).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`,
      icon: DollarSign,
      color: 'var(--accent-emerald)',
      bg: 'rgba(16, 185, 129, 0.1)',
      onClick: () => onNavigateTab('orders'),
    },
  ];

  return (
    <div className="page-wrapper">
      {/* Header */}
      <div className="responsive-header" style={{ marginBottom: '1.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>Autonomous Fulfillment Command Center</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Real-time telemetry, AI extraction pipeline & least-loaded operator task dispatch.
          </p>
        </div>

        <button
          onClick={fetchData}
          disabled={isRefreshing}
          className="btn btn-secondary"
          style={{ padding: '0.5rem 1rem' }}
        >
          <RefreshCw size={15} className={isRefreshing ? 'animate-spin' : ''} />
          <span>{isRefreshing ? 'Refreshing...' : 'Refresh Data'}</span>
        </button>
      </div>

      {/* High Alert Banner for Human Review */}
      {(metrics?.needs_review_count ?? 0) > 0 && (
        <div
          className="glass-panel"
          style={{
            padding: '1.25rem 1.5rem',
            marginBottom: '1.75rem',
            background: 'linear-gradient(90deg, rgba(239, 68, 68, 0.15) 0%, rgba(17, 24, 39, 0.6) 100%)',
            border: '1px solid rgba(239, 68, 68, 0.35)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 'var(--radius-md)',
                background: 'rgba(239, 68, 68, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#f87171',
              }}
            >
              <AlertTriangle size={22} />
            </div>
            <div>
              <div style={{ fontWeight: 600, color: '#fca5a5', fontSize: '0.9375rem' }}>
                {metrics?.needs_review_count} Orders Require Operator Attention
              </div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                Low confidence parsing or ambiguous SKU matches were intercepted by AI validation guardrails.
              </p>
            </div>
          </div>

          <button
            onClick={() => onNavigateTab('review_queue')}
            className="btn btn-primary"
            style={{
              background: 'linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)',
              borderColor: 'rgba(239, 68, 68, 0.5)',
            }}
          >
            <span>Open Review Queue</span>
            <ArrowUpRight size={16} />
          </button>
        </div>
      )}

      {/* Metrics Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '1rem',
          marginBottom: '2rem',
        }}
      >
        {metricCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div
              key={idx}
              className="glass-panel glass-panel-interactive"
              onClick={card.onClick}
              style={{
                padding: '1.25rem',
                cursor: 'pointer',
                borderColor: card.highlight ? 'rgba(239, 68, 68, 0.4)' : undefined,
                minWidth: 0,
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '0.75rem',
                  minWidth: 0,
                }}
              >
                <span
                  style={{
                    fontSize: '0.8125rem',
                    color: 'var(--text-secondary)',
                    fontWeight: 500,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    marginRight: '0.5rem',
                  }}
                  title={card.title}
                >
                  {card.title}
                </span>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 'var(--radius-md)',
                    background: card.bg,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: card.color,
                    flexShrink: 0,
                  }}
                >
                  <Icon size={16} />
                </div>
              </div>
              <div
                className="mono"
                style={{
                  fontSize: 'clamp(1.2rem, 1.8vw, 1.5rem)',
                  fontWeight: 700,
                  color: card.highlight ? '#f87171' : 'var(--text-primary)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  lineHeight: 1.2,
                }}
                title={String(card.value)}
              >
                {card.value}
              </div>
            </div>
          );
        })}
      </div>

      {/* Recent Orders Live Table */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '1.25rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Clock size={18} color="var(--accent-cyan)" />
            <h3 style={{ fontSize: '1.125rem' }}>Recent Order Activity</h3>
          </div>

          <button
            onClick={() => onNavigateTab('orders')}
            className="btn btn-secondary"
            style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
          >
            <span>View All Orders</span>
            <ArrowUpRight size={14} />
          </button>
        </div>

        {recentOrders.length === 0 ? (
          <div
            style={{
              padding: '3rem',
              textAlign: 'center',
              color: 'var(--text-muted)',
            }}
          >
            <Sparkles size={32} style={{ margin: '0 auto 0.75rem', opacity: 0.4 }} />
            <p>No orders recorded yet. Use the "Simulate Inbound Email" button to trigger the pipeline.</p>
          </div>
        ) : (
          <div className="table-container">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>Order #</th>
                  <th>Customer</th>
                  <th>Status</th>
                  <th>Items</th>
                  <th>Total</th>
                  <th>Created</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {recentOrders.map((order) => (
                  <tr key={order.id}>
                    <td className="mono" style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>
                      {order.order_number}
                    </td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{order.customer_name || 'Customer'}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {order.customer_email}
                      </div>
                    </td>
                    <td>
                      <StatusBadge status={order.status} />
                    </td>
                    <td>
                      {order.items?.length > 0 ? (
                        <span style={{ fontSize: '0.8125rem' }}>
                          {order.items.reduce((sum, i) => sum + i.quantity, 0)} units ({order.items.length} SKUs)
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>-</span>
                      )}
                    </td>
                    <td className="mono" style={{ fontWeight: 600 }}>
                      ${Number(order.total_amount ?? 0).toFixed(2)}
                    </td>
                    <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                      {new Date(order.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>
                    <td>
                      <button
                        onClick={() => onViewOrder(order)}
                        className="btn btn-secondary btn-icon"
                        title="View Order Details & Event Timeline"
                        style={{ padding: '0.35rem 0.6rem' }}
                      >
                        <Eye size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
