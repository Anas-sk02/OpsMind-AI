import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/common/Navbar';
import { Sidebar } from './components/common/Sidebar';
import type { AdminTab } from './components/common/Sidebar';
import { LoginView } from './components/auth/LoginView';
import { AdminDashboard } from './components/admin/AdminDashboard';
import { OrdersView } from './components/admin/OrdersView';
import { ReviewQueueView } from './components/admin/ReviewQueueView';
import { InventoryView } from './components/admin/InventoryView';
import { EmployeesView } from './components/admin/EmployeesView';
import { EmailAuditView } from './components/admin/EmailAuditView';
import { PackagingPortal } from './components/packaging/PackagingPortal';
import { DeliveryPortal } from './components/delivery/DeliveryPortal';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import type { Order } from './types';

const MainLayout: React.FC = () => {
  const { user, isLoading } = useAuth();
  const [adminTab, setAdminTab] = useState<AdminTab>('dashboard');
  const [selectedOrderForModal, setSelectedOrderForModal] = useState<Order | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  if (isLoading) {
    return (
      <div
        style={{
          height: '100vh',
          width: '100vw',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--bg-primary)',
          color: 'var(--accent-cyan)',
          fontFamily: 'var(--font-heading)',
          fontSize: '1.25rem',
        }}
      >
        <div className="animate-pulse">Loading OpsMind AI Fulfillment Engine...</div>
      </div>
    );
  }

  if (!user) {
    return <LoginView />;
  }

  // Operator-focused portals
  if (user.role === 'PACKAGING') {
    return (
      <div className="app-container">
        <Navbar />
        <div className="app-body">
          <main className="main-content">
            <ErrorBoundary fallbackTitle="Packaging Portal Error">
              <PackagingPortal />
            </ErrorBoundary>
          </main>
        </div>
      </div>
    );
  }

  if (user.role === 'DELIVERY') {
    return (
      <div className="app-container">
        <Navbar />
        <div className="app-body">
          <main className="main-content">
            <ErrorBoundary fallbackTitle="Delivery Terminal Error">
              <DeliveryPortal />
            </ErrorBoundary>
          </main>
        </div>
      </div>
    );
  }

  // Admin Command Center Portal
  const handleViewOrder = (order: Order) => {
    setSelectedOrderForModal(order);
    setAdminTab('orders');
    setMobileMenuOpen(false);
  };

  return (
    <div className="app-container">
      <Navbar
        onRefresh={() => {}}
        isMobileMenuOpen={mobileMenuOpen}
        onToggleMobileMenu={() => setMobileMenuOpen((prev) => !prev)}
      />
      <div className="app-body">
        <Sidebar
          activeTab={adminTab}
          onSelectTab={setAdminTab}
          isOpen={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
        />
        <main className="main-content">
          <ErrorBoundary fallbackTitle="Admin Portal Error">
            <div style={{ display: adminTab === 'dashboard' ? 'block' : 'none' }}>
              <AdminDashboard
                onNavigateTab={setAdminTab}
                onViewOrder={handleViewOrder}
              />
            </div>

            <div style={{ display: adminTab === 'orders' ? 'block' : 'none' }}>
              <OrdersView
                selectedOrderModal={selectedOrderForModal}
                onCloseModal={() => setSelectedOrderForModal(null)}
              />
            </div>

            <div style={{ display: adminTab === 'review_queue' ? 'block' : 'none' }}>
              <ReviewQueueView />
            </div>

            <div style={{ display: adminTab === 'inventory' ? 'block' : 'none' }}>
              <InventoryView />
            </div>

            <div style={{ display: adminTab === 'employees' ? 'block' : 'none' }}>
              <EmployeesView />
            </div>

            <div style={{ display: adminTab === 'emails' ? 'block' : 'none' }}>
              <EmailAuditView />
            </div>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
};

export default function App() {
  return (
    <AuthProvider>
      <MainLayout />
    </AuthProvider>
  );
}
