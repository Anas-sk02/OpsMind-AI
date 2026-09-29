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
  };

  return (
    <div className="app-container">
      <Navbar onRefresh={() => {}} />
      <div className="app-body">
        <Sidebar activeTab={adminTab} onSelectTab={setAdminTab} />
        <main className="main-content">
          <ErrorBoundary fallbackTitle="Admin Portal Error">
            {adminTab === 'dashboard' && (
              <AdminDashboard
                onNavigateTab={setAdminTab}
                onViewOrder={handleViewOrder}
              />
            )}

            {adminTab === 'orders' && (
              <OrdersView
                selectedOrderModal={selectedOrderForModal}
                onCloseModal={() => setSelectedOrderForModal(null)}
              />
            )}

            {adminTab === 'review_queue' && <ReviewQueueView />}

            {adminTab === 'inventory' && <InventoryView />}

            {adminTab === 'employees' && <EmployeesView />}

            {adminTab === 'emails' && <EmailAuditView />}
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
