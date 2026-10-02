import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { StatusBadge } from '../common/StatusBadge';
import {
  Box,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  PackageCheck,
  X,
} from 'lucide-react';
import type { Task } from '../../types';

export const PackagingPortal: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [checkedItems, setCheckedItems] = useState<Record<string, boolean>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Exception modal
  const [isExceptionOpen, setIsExceptionOpen] = useState(false);
  const [exceptionReason, setExceptionReason] = useState('Damaged goods in bin');

  const fetchMyTasks = async () => {
    setIsRefreshing(true);
    try {
      const myTasks = await api.getMyTasks();
      const packagingTasks = (myTasks || []).filter((t) => t.task_type === 'PACKAGING' && t.status !== 'COMPLETED');
      setTasks(packagingTasks);
      if (packagingTasks.length > 0 && (!activeTask || !packagingTasks.find((t) => t.id === activeTask.id))) {
        selectTask(packagingTasks[0]);
      } else if (packagingTasks.length === 0) {
        setActiveTask(null);
      }
    } catch (err) {
      console.error('Failed to load packaging tasks:', err);
    } finally {
      setTimeout(() => {
        setIsRefreshing(false);
      }, 350);
    }
  };

  useEffect(() => {
    fetchMyTasks();
  }, []);

  const selectTask = (task: Task) => {
    setActiveTask(task);
    const initialChecked: Record<string, boolean> = {};
    const taskItems = task.items || task.order?.items || [];
    taskItems.forEach((item) => {
      initialChecked[item.id] = false;
    });
    setCheckedItems(initialChecked);
  };

  const toggleCheckItem = (itemId: string) => {
    setCheckedItems((prev) => ({
      ...prev,
      [itemId]: !prev[itemId],
    }));
  };

  const activeItems = activeTask?.items || activeTask?.order?.items || [];
  const allItemsChecked =
    activeItems.length > 0
      ? activeItems.every((i) => checkedItems[i.id])
      : true;

  const handleCompletePackaging = async () => {
    if (!activeTask) return;
    setIsSubmitting(true);
    try {
      await api.completeTask(activeTask.id, {
        notes: 'All items verified and packaged in parcel.',
      });
      await fetchMyTasks();
    } catch (err: any) {
      alert(`Failed to complete packaging: ${err.message}`);
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
      alert(`Exception report failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page-wrapper">
      {/* Header */}
      <div className="responsive-header" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 'var(--radius-md)',
              background: 'rgba(59, 130, 246, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-blue)',
            }}
          >
            <Box size={24} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Warehouse Packaging Terminal</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
              Verify physical item SKUs, box parcels, and transition orders to PACKED.
            </p>
          </div>
        </div>

        <button onClick={fetchMyTasks} disabled={isRefreshing} className="btn btn-secondary">
          <RefreshCw size={15} className={isRefreshing ? 'animate-spin' : ''} />
          <span>{isRefreshing ? 'Refreshing...' : 'Refresh Tasks'}</span>
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
          <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>All Packaging Tasks Finished!</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            No pending packaging assignments. New tasks will be auto-allocated as orders are confirmed.
          </p>
        </div>
      ) : (
        <div className="portal-split-layout">
          {/* Left Column: Task Queue */}
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
              My Assigned Queue ({tasks.length})
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {tasks.map((task) => {
                const isSelected = activeTask?.id === task.id;
                return (
                  <div
                    key={task.id}
                    onClick={() => selectTask(task)}
                    style={{
                      padding: '1rem',
                      borderRadius: 'var(--radius-md)',
                      background: isSelected ? 'rgba(59, 130, 246, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                      border: isSelected ? '1px solid var(--accent-blue)' : '1px solid var(--border-color)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                      <span className="mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>
                        {task.order_number || task.order?.order_number || `Order ${task.order_id.slice(0, 8)}`}
                      </span>
                      <span className="badge" style={{ background: 'rgba(59, 130, 246, 0.2)', color: 'var(--accent-blue)' }}>
                        {task.status}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                      {(task.items || task.order?.items)?.length
                        ? `${(task.items || task.order?.items)!.length} SKUs to pack`
                        : 'Items checklist ready'}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Interactive SKU Checklist & Pack Confirmation */}
          {activeTask && (
            <div className="glass-panel" style={{ padding: '1.75rem' }}>
              {/* Order Info Banner */}
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
                    <StatusBadge status={activeTask.order_status || activeTask.order?.status || 'PACKAGING'} />
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                    Recipient: {activeTask.customer_name || activeTask.order?.customer_name || 'Customer'} | {activeTask.delivery_address || activeTask.order?.shipping_address || 'Warehouse Pick'}
                  </div>
                </div>

                <button
                  onClick={() => setIsExceptionOpen(true)}
                  className="btn btn-danger"
                  style={{ fontSize: '0.8125rem' }}
                >
                  <AlertTriangle size={15} />
                  <span>Report Exception</span>
                </button>
              </div>

              {/* SKU Verification Checklist */}
              <div style={{ marginBottom: '2rem' }}>
                <div
                  style={{
                    fontSize: '0.8125rem',
                    fontWeight: 600,
                    color: 'var(--text-muted)',
                    textTransform: 'uppercase',
                    marginBottom: '1rem',
                  }}
                >
                  Physical Item Verification Checklist
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {activeItems.length > 0 ? (
                    activeItems.map((item) => {
                      const isChecked = checkedItems[item.id] || false;
                      return (
                        <div
                          key={item.id}
                          onClick={() => toggleCheckItem(item.id)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '1rem 1.25rem',
                            borderRadius: 'var(--radius-md)',
                            background: isChecked ? 'rgba(16, 185, 129, 0.1)' : 'rgba(255, 255, 255, 0.03)',
                            border: isChecked ? '1px solid var(--accent-emerald)' : '1px solid var(--border-color)',
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => {}}
                              style={{ width: 20, height: 20, accentColor: 'var(--accent-emerald)', cursor: 'pointer' }}
                            />
                            <div>
                              <div style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{item.product_name}</div>
                              <div className="mono" style={{ fontSize: '0.8125rem', color: 'var(--accent-cyan)' }}>
                                SKU: {item.product_sku || (item as any).sku}
                              </div>
                            </div>
                          </div>

                          <div className="mono" style={{ fontSize: '1.125rem', fontWeight: 700 }}>
                            QTY: {item.quantity}
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div style={{ padding: '1rem', color: 'var(--text-muted)' }}>
                      No items attached to this task.
                    </div>
                  )}
                </div>
              </div>

              {/* Primary Action Button */}
              <div>
                <button
                  onClick={handleCompletePackaging}
                  disabled={isSubmitting || !allItemsChecked}
                  className="btn btn-success"
                  style={{
                    width: '100%',
                    padding: '1rem',
                    fontSize: '1rem',
                    fontWeight: 700,
                    letterSpacing: '0.02em',
                    boxShadow: allItemsChecked ? '0 0 20px rgba(16, 185, 129, 0.3)' : 'none',
                    opacity: allItemsChecked ? 1 : 0.5,
                  }}
                >
                  <PackageCheck size={20} />
                  <span>
                    {isSubmitting
                      ? 'Confirming Parcel Packaging...'
                      : allItemsChecked
                      ? 'MARK AS PACKED -> DISPATCH TO DELIVERY'
                      : 'CHECK ALL ITEMS ABOVE TO PROCEED'}
                  </span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Exception Modal */}
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
              <h3 style={{ fontSize: '1.125rem', color: '#f87171' }}>Report Packaging Exception</h3>
              <button className="btn btn-secondary btn-icon" onClick={() => setIsExceptionOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleReportException} style={{ padding: '1.5rem' }}>
              <div className="form-group">
                <label className="form-label">Exception Details / Damage Notes</label>
                <textarea
                  required
                  rows={4}
                  className="form-textarea"
                  placeholder="Describe missing inventory, damaged packaging, or physical mismatch..."
                  value={exceptionReason}
                  onChange={(e) => setExceptionReason(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsExceptionOpen(false)}>
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="btn btn-danger">
                  {isSubmitting ? 'Reporting...' : 'Submit Exception Flag'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
