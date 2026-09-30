import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import {
  UserPlus,
  Box,
  Truck,
  ShieldCheck,
  RefreshCw,
  X,
  Activity,
  ArrowRightLeft,
} from 'lucide-react';
import type { User, Task } from '../../types';

export const EmployeesView: React.FC = () => {
  const [employees, setEmployees] = useState<User[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  // Modals
  const [isAddStaffOpen, setIsAddStaffOpen] = useState(false);
  const [isReassignOpen, setIsReassignOpen] = useState(false);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [newAssigneeId, setNewAssigneeId] = useState('');
  const [reassignReason, setReassignReason] = useState('Workload rebalancing');

  // Form State
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('Operator@123456!');
  const [role, setRole] = useState<'PACKAGING' | 'DELIVERY' | 'ADMIN'>('PACKAGING');
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [empData, taskData, metricsData] = await Promise.all([
        api.getEmployees(),
        api.getAllTasks({ status: 'PENDING', page_size: 50 }),
        api.getEmployeeWorkloadMetrics().catch(() => []),
      ]);

      const metricsMap = new Map((metricsData || []).map((m: any) => [m.employee_id, m.active_tasks]));
      const taskList = taskData.data || [];

      const enrichedEmployees = (empData || []).map((emp) => {
        const fallbackCount = taskList.filter(
          (t) => t.assigned_employee_id === emp.id && ['PENDING', 'IN_PROGRESS'].includes(t.status)
        ).length;
        const activeCount = metricsMap.has(emp.id) ? (metricsMap.get(emp.id) ?? 0) : fallbackCount;
        return {
          ...emp,
          active_tasks_count: Math.max(activeCount, fallbackCount),
        };
      });

      setEmployees(enrichedEmployees);
      setTasks(taskList);
    } catch (err) {
      console.error('Failed to load employees & tasks:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormSubmitting(true);
    setFormError(null);
    try {
      await api.createEmployee({
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        password,
        role,
      });
      setIsAddStaffOpen(false);
      setFullName('');
      setEmail('');
      await fetchData();
    } catch (err: any) {
      setFormError(err.message || 'Failed to create employee');
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleReassignTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTask || !newAssigneeId) return;
    setFormSubmitting(true);
    setFormError(null);
    try {
      await api.reassignTask(selectedTask.id, newAssigneeId, reassignReason);
      setIsReassignOpen(false);
      await fetchData();
    } catch (err: any) {
      setFormError(err.message || 'Task reassignment failed');
    } finally {
      setFormSubmitting(false);
    }
  };

  return (
    <div className="page-wrapper">
      {/* Header */}
      <div className="responsive-header" style={{ marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>Staff & Workload Allocation</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Least-loaded autonomous task dispatch, active operator workloads & manual reassignments.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button onClick={fetchData} disabled={loading} className="btn btn-secondary">
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          <button onClick={() => setIsAddStaffOpen(true)} className="btn btn-primary">
            <UserPlus size={16} />
            <span>Add Staff Member</span>
          </button>
        </div>
      </div>

      {/* Staff Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '1.25rem',
          marginBottom: '2rem',
        }}
      >
        {employees.map((emp) => {
          const fallbackCount = tasks.filter(
            (t) => t.assigned_employee_id === emp.id && ['PENDING', 'IN_PROGRESS'].includes(t.status)
          ).length;
          const activeTasksCount = Math.max(emp.active_tasks_count ?? 0, fallbackCount);
          const maxCapacity = 5; // Visual baseline
          const percent = Math.min((activeTasksCount / maxCapacity) * 100, 100);

          return (
            <div key={emp.id} className="glass-panel" style={{ padding: '1.25rem' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '1rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: 'var(--radius-md)',
                      background:
                        emp.role === 'ADMIN'
                          ? 'rgba(56, 189, 248, 0.15)'
                          : emp.role === 'PACKAGING'
                          ? 'rgba(59, 130, 246, 0.15)'
                          : 'rgba(245, 158, 11, 0.15)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color:
                        emp.role === 'ADMIN'
                          ? 'var(--accent-cyan)'
                          : emp.role === 'PACKAGING'
                          ? 'var(--accent-blue)'
                          : 'var(--accent-amber)',
                    }}
                  >
                    {emp.role === 'ADMIN' ? (
                      <ShieldCheck size={20} />
                    ) : emp.role === 'PACKAGING' ? (
                      <Box size={20} />
                    ) : (
                      <Truck size={20} />
                    )}
                  </div>
                  <div>
                    <div style={{ fontWeight: 600 }}>{emp.full_name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{emp.email}</div>
                  </div>
                </div>

                <span
                  className="badge"
                  style={{
                    background: emp.is_active ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                    color: emp.is_active ? '#34d399' : '#f87171',
                  }}
                >
                  {emp.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>

              {/* Workload Progress Bar */}
              <div>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '0.75rem',
                    marginBottom: '0.35rem',
                  }}
                >
                  <span style={{ color: 'var(--text-secondary)' }}>Current Workload</span>
                  <span className="mono" style={{ fontWeight: 600 }}>
                    {activeTasksCount} Active Tasks
                  </span>
                </div>

                <div
                  style={{
                    height: 6,
                    borderRadius: 'var(--radius-full)',
                    background: 'rgba(255, 255, 255, 0.05)',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${percent}%`,
                      background:
                        activeTasksCount > 3
                          ? 'var(--accent-rose)'
                          : activeTasksCount > 1
                          ? 'var(--accent-amber)'
                          : 'var(--accent-emerald)',
                      transition: 'width 0.3s ease',
                    }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Active Tasks Table & Reassignment */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
          <Activity size={18} color="var(--accent-cyan)" />
          <h3 style={{ fontSize: '1.125rem' }}>Pending Task Queue</h3>
        </div>

        <div className="table-container">
          <table className="ops-table">
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Order Ref</th>
                <th>Task Type</th>
                <th>Assigned Operator</th>
                <th>Status</th>
                <th>Created</th>
                <th>Reassign</th>
              </tr>
            </thead>
            <tbody>
              {tasks.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                    No pending tasks in queue. Tasks are generated automatically when orders are confirmed.
                  </td>
                </tr>
              ) : (
                tasks.map((task) => (
                  <tr key={task.id}>
                    <td className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {task.id.slice(0, 8)}...
                    </td>
                    <td className="mono" style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>
                      {task.order?.order_number || `${task.order_id.slice(0, 8)}...`}
                    </td>
                    <td>
                      <span
                        className="badge"
                        style={{
                          background:
                            task.task_type === 'PACKAGING'
                              ? 'rgba(59, 130, 246, 0.15)'
                              : 'rgba(245, 158, 11, 0.15)',
                          color:
                            task.task_type === 'PACKAGING'
                              ? 'var(--accent-blue)'
                              : 'var(--accent-amber)',
                        }}
                      >
                        {task.task_type}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontWeight: 500 }}>
                        {task.assigned_employee_name || 'Assigned Operator'}
                      </span>
                    </td>
                    <td>
                      <span className="badge" style={{ background: 'rgba(255, 255, 255, 0.05)', color: 'var(--text-secondary)' }}>
                        {task.status}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                      {new Date(task.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td>
                      <button
                        onClick={() => {
                          setSelectedTask(task);
                          setIsReassignOpen(true);
                        }}
                        className="btn btn-secondary"
                        style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}
                      >
                        <ArrowRightLeft size={13} />
                        <span>Reassign</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Staff Member Modal */}
      {isAddStaffOpen && (
        <div className="modal-overlay" onClick={() => setIsAddStaffOpen(false)}>
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
              <h3 style={{ fontSize: '1.125rem' }}>Add Operator / Staff Member</h3>
              <button className="btn btn-secondary btn-icon" onClick={() => setIsAddStaffOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateEmployee} style={{ padding: '1.5rem' }}>
              {formError && (
                <div
                  style={{
                    padding: '0.75rem',
                    marginBottom: '1rem',
                    borderRadius: 'var(--radius-md)',
                    background: 'rgba(239, 68, 68, 0.15)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    color: '#fca5a5',
                    fontSize: '0.8125rem',
                  }}
                >
                  {formError}
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  type="text"
                  required
                  placeholder="Jane Operator"
                  className="form-input"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Work Email</label>
                <input
                  type="email"
                  required
                  placeholder="jane.packager@opsmind.io"
                  className="form-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Role Assignment</label>
                  <select
                    className="form-select"
                    value={role}
                    onChange={(e) => setRole(e.target.value as any)}
                  >
                    <option value="PACKAGING">Packaging Operator</option>
                    <option value="DELIVERY">Delivery Driver</option>
                    <option value="ADMIN">System Administrator</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Temporary Password</label>
                  <input
                    type="text"
                    required
                    className="form-input mono"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsAddStaffOpen(false)}>
                  Cancel
                </button>
                <button type="submit" disabled={formSubmitting} className="btn btn-primary">
                  {formSubmitting ? 'Creating...' : 'Register Staff Member'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reassign Task Modal */}
      {isReassignOpen && selectedTask && (
        <div className="modal-overlay" onClick={() => setIsReassignOpen(false)}>
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
              <div>
                <h3 style={{ fontSize: '1.125rem' }}>Reassign Task</h3>
                <p className="mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                  Task {selectedTask.id.slice(0, 8)}... ({selectedTask.task_type})
                </p>
              </div>
              <button className="btn btn-secondary btn-icon" onClick={() => setIsReassignOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleReassignTask} style={{ padding: '1.5rem' }}>
              <div className="form-group">
                <label className="form-label">Select Target Operator</label>
                <select
                  required
                  className="form-select"
                  value={newAssigneeId}
                  onChange={(e) => setNewAssigneeId(e.target.value)}
                >
                  <option value="">-- Choose Operator --</option>
                  {employees
                    .filter((e) => e.role === selectedTask.task_type && e.is_active)
                    .map((emp) => (
                      <option key={emp.id} value={emp.id}>
                        {emp.full_name} ({emp.active_tasks_count ?? 0} active tasks)
                      </option>
                    ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Reassignment Reason</label>
                <input
                  type="text"
                  required
                  className="form-input"
                  value={reassignReason}
                  onChange={(e) => setReassignReason(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsReassignOpen(false)}>
                  Cancel
                </button>
                <button type="submit" disabled={formSubmitting} className="btn btn-primary">
                  {formSubmitting ? 'Reassigning...' : 'Confirm Reassignment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
