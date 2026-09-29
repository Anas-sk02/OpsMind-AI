import React from 'react';
import {
  LayoutDashboard,
  ShoppingCart,
  AlertTriangle,
  Boxes,
  Users,
  Mail,
  Flame,
} from 'lucide-react';

export type AdminTab =
  | 'dashboard'
  | 'orders'
  | 'review_queue'
  | 'inventory'
  | 'employees'
  | 'emails';

interface SidebarProps {
  activeTab: AdminTab;
  onSelectTab: (tab: AdminTab) => void;
  reviewCount?: number;
  lowStockCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  reviewCount = 0,
  lowStockCount = 0,
}) => {
  const navItems = [
    { id: 'dashboard', label: 'Overview', icon: LayoutDashboard },
    { id: 'orders', label: 'Order Timeline', icon: ShoppingCart },
    {
      id: 'review_queue',
      label: 'Review Queue',
      icon: AlertTriangle,
      badge: reviewCount > 0 ? reviewCount : undefined,
      badgeColor: 'var(--accent-amber)',
    },
    {
      id: 'inventory',
      label: 'Products & Ledger',
      icon: Boxes,
      badge: lowStockCount > 0 ? lowStockCount : undefined,
      badgeColor: 'var(--accent-rose)',
    },
    { id: 'employees', label: 'Staff & Workload', icon: Users },
    { id: 'emails', label: 'Email Stream', icon: Mail },
  ];

  return (
    <aside
      style={{
        width: 240,
        background: 'rgba(17, 24, 39, 0.65)',
        backdropFilter: 'blur(16px)',
        borderRight: '1px solid var(--border-color)',
        display: 'flex',
        flexDirection: 'column',
        padding: '1.25rem 0.75rem',
        flexShrink: 0,
      }}
    >
      <div style={{ marginBottom: '1rem', padding: '0 0.5rem' }}>
        <span
          style={{
            fontSize: '0.6875rem',
            fontWeight: 700,
            color: 'var(--text-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}
        >
          Management Portal
        </span>
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id as AdminTab)}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.65rem 0.875rem',
                borderRadius: 'var(--radius-md)',
                background: isActive ? 'rgba(56, 189, 248, 0.12)' : 'transparent',
                color: isActive ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                border: isActive
                  ? '1px solid rgba(56, 189, 248, 0.25)'
                  : '1px solid transparent',
                fontSize: '0.875rem',
                fontWeight: isActive ? 600 : 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                width: '100%',
                textAlign: 'left',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <Icon size={18} />
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && (
                <span
                  style={{
                    background: item.badgeColor || 'var(--accent-cyan)',
                    color: '#000',
                    fontSize: '0.6875rem',
                    fontWeight: 700,
                    padding: '0.1rem 0.45rem',
                    borderRadius: 'var(--radius-full)',
                  }}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Zero Customer Login Rule Reminder in Footer */}
      <div
        style={{
          marginTop: 'auto',
          padding: '0.875rem',
          borderRadius: 'var(--radius-md)',
          background: 'rgba(56, 189, 248, 0.05)',
          border: '1px solid rgba(56, 189, 248, 0.15)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
          <Flame size={14} color="var(--accent-cyan)" />
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>
            Zero-Login Rule
          </span>
        </div>
        <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
          Customers never have portals or credentials. All interactions occur strictly via email.
        </p>
      </div>
    </aside>
  );
};
