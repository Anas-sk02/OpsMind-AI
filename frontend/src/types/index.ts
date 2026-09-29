export type UserRole = 'ADMIN' | 'PACKAGING' | 'DELIVERY';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  active_tasks_count?: number;
}

export type OrderStatus =
  | 'RECEIVED'
  | 'PROCESSING'
  | 'CONFIRMED'
  | 'PACKAGING'
  | 'PACKED'
  | 'OUT_FOR_DELIVERY'
  | 'DELIVERED'
  | 'NEEDS_REVIEW'
  | 'OUT_OF_STOCK'
  | 'CANCELLED';

export interface Customer {
  id: string;
  email: string;
  name: string;
  phone?: string | null;
  shipping_address?: string | null;
  preferred_language: string;
  created_at: string;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  description?: string | null;
  price: number;
  is_active: boolean;
  available_qty: number;
  reserved_qty: number;
  total_qty: number;
  reorder_level: number;
  is_low_stock: boolean;
}

export interface OrderItem {
  id: string;
  order_id: string;
  product_id: string;
  sku?: string;
  product_sku?: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

export interface OrderEvent {
  id: string;
  order_id: string;
  from_status?: OrderStatus | null;
  to_status?: OrderStatus | null;
  event_type: string;
  description?: string | null;
  actor_id?: string | null;
  metadata?: Record<string, any> | null;
  created_at: string;
}

export interface Task {
  id: string;
  order_id: string;
  order_number?: string;
  assigned_employee_id?: string;
  assigned_employee_name?: string;
  task_type: 'PACKAGING' | 'DELIVERY';
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'EXCEPTION' | 'FAILED' | 'CANCELLED';
  exception_notes?: string | null;
  created_at: string;
  completed_at?: string | null;
  customer_name?: string;
  customer_email?: string;
  delivery_address?: string;
  order_status?: string;
  items?: OrderItem[];
  order?: Order;
}

export interface Order {
  id: string;
  order_number: string;
  customer_id: string;
  customer_name?: string;
  customer_email?: string;
  customer_phone?: string;
  shipping_address: string;
  status: OrderStatus;
  total_amount: number;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
  events?: OrderEvent[];
  tasks?: Task[];
}

export interface InventoryMovement {
  id: string;
  product_id: string;
  product_sku?: string;
  product_name?: string;
  delta_qty: number;
  movement_type: 'PURCHASE_RECEIPT' | 'ORDER_RESERVED' | 'ORDER_RELEASED' | 'ORDER_DEDUCTED' | 'MANUAL_ADJUSTMENT';
  reason?: string | null;
  order_id?: string | null;
  actor_user_id?: string | null;
  created_at: string;
}

export interface EmailMessage {
  id: string;
  message_id: string;
  customer_id?: string | null;
  order_id?: string | null;
  direction: 'INBOUND' | 'OUTBOUND';
  sender_email: string;
  recipient_email: string;
  subject: string;
  body_plain: string;
  body_html?: string | null;
  detected_language: string;
  ai_extraction_payload?: Record<string, any> | null;
  created_at: string;
}

export interface DashboardMetrics {
  total_orders: number;
  active_orders: number;
  pending_packaging: number;
  out_for_delivery: number;
  needs_review_count: number;
  low_stock_count: number;
  total_revenue: number;
}
