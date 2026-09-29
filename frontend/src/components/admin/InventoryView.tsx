import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import {
  Plus,
  ArrowUpDown,
  History,
  AlertCircle,
  X,
  RefreshCw,
  Search,
} from 'lucide-react';
import type { Product, InventoryMovement } from '../../types';

export const InventoryView: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [lowStockFilter, setLowStockFilter] = useState(false);

  // Modals
  const [isAddProductOpen, setIsAddProductOpen] = useState(false);
  const [isAdjustStockOpen, setIsAdjustStockOpen] = useState(false);
  const [isMovementsOpen, setIsMovementsOpen] = useState(false);

  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [productMovements, setProductMovements] = useState<InventoryMovement[]>([]);

  // Add Product Form state
  const [newSku, setNewSku] = useState('');
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newPrice, setNewPrice] = useState('49.99');
  const [newStock, setNewStock] = useState('20');
  const [newReorder, setNewReorder] = useState('5');

  // Adjust Stock Form state
  const [adjustDelta, setAdjustDelta] = useState('10');
  const [adjustType, setAdjustType] = useState('PURCHASE_RECEIPT');
  const [adjustReason, setAdjustReason] = useState('Restock shipment received');

  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const res = await api.getProducts({
        low_stock_only: lowStockFilter ? true : undefined,
        search: searchQuery || undefined,
        page_size: 100,
      });
      setProducts(res.data || []);
    } catch (err) {
      console.error('Failed to load products:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, [lowStockFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchProducts();
  };

  const handleCreateProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormSubmitting(true);
    setFormError(null);
    try {
      await api.createProduct({
        sku: newSku.toUpperCase().trim(),
        name: newName.trim(),
        description: newDesc.trim() || undefined,
        price: parseFloat(newPrice),
        initial_stock: parseInt(newStock, 10),
        reorder_level: parseInt(newReorder, 10),
      });
      setIsAddProductOpen(false);
      setNewSku('');
      setNewName('');
      setNewDesc('');
      await fetchProducts();
    } catch (err: any) {
      setFormError(err.message || 'Failed to create product');
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleAdjustStock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProduct) return;
    setFormSubmitting(true);
    setFormError(null);
    try {
      await api.adjustStock(selectedProduct.id, {
        delta_qty: parseInt(adjustDelta, 10),
        movement_type: adjustType,
        reason: adjustReason,
      });
      setIsAdjustStockOpen(false);
      await fetchProducts();
    } catch (err: any) {
      setFormError(err.message || 'Stock adjustment failed');
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleOpenMovements = async (prod: Product) => {
    setSelectedProduct(prod);
    setIsMovementsOpen(true);
    try {
      const movements = await api.getProductMovements(prod.id);
      setProductMovements(movements);
    } catch (err) {
      console.error('Failed to load movements:', err);
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
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700 }}>Inventory & Stock Ledger</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Multi-SKU catalog, real-time reserved vs. available quantities & immutable movement ledger.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button onClick={fetchProducts} disabled={loading} className="btn btn-secondary">
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          <button onClick={() => setIsAddProductOpen(true)} className="btn btn-primary">
            <Plus size={16} />
            <span>Add New Product</span>
          </button>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div
        className="glass-panel"
        style={{
          padding: '1rem',
          marginBottom: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <form onSubmit={handleSearchSubmit} style={{ flex: 1, minWidth: 260, position: 'relative' }}>
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
            placeholder="Search by SKU or Product Name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: '2.25rem' }}
          />
        </form>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            onClick={() => setLowStockFilter(!lowStockFilter)}
            className="btn btn-secondary"
            style={{
              fontSize: '0.8125rem',
              background: lowStockFilter ? 'rgba(239, 68, 68, 0.15)' : undefined,
              borderColor: lowStockFilter ? 'rgba(239, 68, 68, 0.4)' : undefined,
              color: lowStockFilter ? '#f87171' : undefined,
            }}
          >
            <AlertCircle size={15} />
            <span>Low Stock Alerts Only</span>
          </button>
        </div>
      </div>

      {/* Products Table */}
      <div className="table-container">
        <table className="ops-table">
          <thead>
            <tr>
              <th>SKU</th>
              <th>Product Name</th>
              <th>Unit Price</th>
              <th>Available</th>
              <th>Reserved</th>
              <th>Total Stock</th>
              <th>Reorder Point</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {products.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                  No products in catalog. Click "Add New Product" to seed inventory.
                </td>
              </tr>
            ) : (
              products.map((prod) => (
                <tr key={prod.id}>
                  <td className="mono" style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>
                    {prod.sku}
                  </td>
                  <td>
                    <div style={{ fontWeight: 500 }}>{prod.name}</div>
                    {prod.description && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {prod.description}
                      </div>
                    )}
                  </td>
                  <td className="mono" style={{ fontWeight: 600 }}>
                    ${prod.price.toFixed(2)}
                  </td>
                  <td className="mono" style={{ fontWeight: 700, color: prod.available_qty <= prod.reorder_level ? '#f87171' : 'var(--accent-emerald)' }}>
                    {prod.available_qty}
                  </td>
                  <td className="mono" style={{ color: 'var(--accent-amber)' }}>
                    {prod.reserved_qty}
                  </td>
                  <td className="mono">{prod.total_qty}</td>
                  <td className="mono" style={{ color: 'var(--text-muted)' }}>
                    {prod.reorder_level}
                  </td>
                  <td>
                    {prod.available_qty === 0 ? (
                      <span className="badge" style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', borderColor: 'rgba(239, 68, 68, 0.3)' }}>
                        <span className="badge-dot" style={{ background: '#ef4444' }} /> Depleted
                      </span>
                    ) : prod.is_low_stock ? (
                      <span className="badge" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', borderColor: 'rgba(245, 158, 11, 0.3)' }}>
                        <span className="badge-dot" style={{ background: '#f59e0b' }} /> Low Stock
                      </span>
                    ) : (
                      <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', borderColor: 'rgba(16, 185, 129, 0.3)' }}>
                        <span className="badge-dot" style={{ background: '#10b981' }} /> In Stock
                      </span>
                    )}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.35rem' }}>
                      <button
                        onClick={() => {
                          setSelectedProduct(prod);
                          setIsAdjustStockOpen(true);
                        }}
                        className="btn btn-secondary"
                        style={{ fontSize: '0.75rem', padding: '0.35rem 0.6rem' }}
                        title="Adjust Stock"
                      >
                        <ArrowUpDown size={13} />
                        <span>Adjust</span>
                      </button>

                      <button
                        onClick={() => handleOpenMovements(prod)}
                        className="btn btn-secondary btn-icon"
                        style={{ padding: '0.35rem 0.6rem' }}
                        title="View Immutable Movement Audit Ledger"
                      >
                        <History size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Add Product Modal */}
      {isAddProductOpen && (
        <div className="modal-overlay" onClick={() => setIsAddProductOpen(false)}>
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
              <h3 style={{ fontSize: '1.125rem' }}>Add New Catalog Product</h3>
              <button className="btn btn-secondary btn-icon" onClick={() => setIsAddProductOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateProduct} style={{ padding: '1.5rem' }}>
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

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">SKU Code</label>
                  <input
                    type="text"
                    required
                    placeholder="SKU-PRO-01"
                    className="form-input mono"
                    value={newSku}
                    onChange={(e) => setNewSku(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Product Name</label>
                  <input
                    type="text"
                    required
                    placeholder="Mechanical Gaming Keyboard"
                    className="form-input"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Description (Optional)</label>
                <input
                  type="text"
                  placeholder="Ergonomic RGB tactile switches"
                  className="form-input"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Unit Price ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    className="form-input mono"
                    value={newPrice}
                    onChange={(e) => setNewPrice(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Initial Stock</label>
                  <input
                    type="number"
                    required
                    className="form-input mono"
                    value={newStock}
                    onChange={(e) => setNewStock(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Reorder Level</label>
                  <input
                    type="number"
                    required
                    className="form-input mono"
                    value={newReorder}
                    onChange={(e) => setNewReorder(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsAddProductOpen(false)}>
                  Cancel
                </button>
                <button type="submit" disabled={formSubmitting} className="btn btn-primary">
                  {formSubmitting ? 'Saving...' : 'Create Product'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Adjust Stock Drawer / Modal */}
      {isAdjustStockOpen && selectedProduct && (
        <div className="modal-overlay" onClick={() => setIsAdjustStockOpen(false)}>
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
                <h3 style={{ fontSize: '1.125rem' }}>Adjust Inventory Stock</h3>
                <p className="mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                  {selectedProduct.sku} — {selectedProduct.name}
                </p>
              </div>
              <button className="btn btn-secondary btn-icon" onClick={() => setIsAdjustStockOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAdjustStock} style={{ padding: '1.5rem' }}>
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

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Delta Quantity (+ or -)</label>
                  <input
                    type="number"
                    required
                    className="form-input mono"
                    value={adjustDelta}
                    onChange={(e) => setAdjustDelta(e.target.value)}
                  />
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    Current available: {selectedProduct.available_qty} units
                  </span>
                </div>

                <div className="form-group">
                  <label className="form-label">Adjustment Type</label>
                  <select
                    className="form-select"
                    value={adjustType}
                    onChange={(e) => setAdjustType(e.target.value)}
                  >
                    <option value="PURCHASE_RECEIPT">Purchase Receipt (+ Inbound)</option>
                    <option value="MANUAL_ADJUSTMENT">Manual Reconciliation (+ / -)</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Reason / Notes (Mandatory for Audit)</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Inbound PO #9821 from supplier"
                  className="form-input"
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1rem' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsAdjustStockOpen(false)}>
                  Cancel
                </button>
                <button type="submit" disabled={formSubmitting} className="btn btn-primary">
                  {formSubmitting ? 'Recording Ledger...' : 'Commit Stock Movement'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Movement Ledger Audit Modal */}
      {isMovementsOpen && selectedProduct && (
        <div className="modal-overlay" onClick={() => setIsMovementsOpen(false)}>
          <div className="modal-content modal-content-lg" onClick={(e) => e.stopPropagation()}>
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
                <h3 style={{ fontSize: '1.125rem' }}>Immutable Movement Ledger</h3>
                <p className="mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                  SKU: {selectedProduct.sku} | Total Units: {selectedProduct.total_qty}
                </p>
              </div>
              <button className="btn btn-secondary btn-icon" onClick={() => setIsMovementsOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: '1.5rem' }}>
              <div className="table-container">
                <table className="ops-table">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Delta Units</th>
                      <th>Movement Type</th>
                      <th>Reason / Context</th>
                      <th>Order Ref</th>
                    </tr>
                  </thead>
                  <tbody>
                    {productMovements.length === 0 ? (
                      <tr>
                        <td colSpan={5} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                          No movements recorded yet for this SKU.
                        </td>
                      </tr>
                    ) : (
                      productMovements.map((m) => (
                        <tr key={m.id}>
                          <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                            {new Date(m.created_at).toLocaleString()}
                          </td>
                          <td
                            className="mono"
                            style={{
                              fontWeight: 700,
                              color: m.delta_qty > 0 ? 'var(--accent-emerald)' : '#f87171',
                            }}
                          >
                            {m.delta_qty > 0 ? `+${m.delta_qty}` : m.delta_qty}
                          </td>
                          <td>
                            <span className="badge" style={{ background: 'rgba(255, 255, 255, 0.05)', color: 'var(--text-secondary)' }}>
                              {m.movement_type}
                            </span>
                          </td>
                          <td style={{ fontSize: '0.8125rem' }}>{m.reason || '-'}</td>
                          <td className="mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                            {m.order_id ? `${m.order_id.slice(0, 8)}...` : '-'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
