import type {
  User,
  Order,
  Product,
  Task,
  InventoryMovement,
  EmailMessage,
  DashboardMetrics,
} from '../types';

const BASE_URL = '/api/v1';

class ApiClient {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem('opsmind_token');
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('opsmind_token', token);
    } else {
      localStorage.removeItem('opsmind_token');
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<{ data: T; meta?: any }> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      // Clear token on 401
      this.setToken(null);
      window.dispatchEvent(new Event('auth:unauthorized'));
    }

    const json = await response.json().catch(() => ({}));

    if (!response.ok) {
      const errorMsg =
        json?.error?.message ||
        json?.detail ||
        `Request failed with status ${response.status}`;
      throw new Error(errorMsg);
    }

    return json;
  }

  // Auth Endpoints
  async login(email: string, password: string): Promise<{ access_token: string; refresh_token?: string; user: User }> {
    const response = await fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const json = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(json?.error?.message || json?.detail || 'Login failed');
    }

    const tokenData = json.data || json;
    this.setToken(tokenData.access_token);
    return tokenData;
  }

  async getMe(): Promise<User> {
    const res = await this.request<User>('/auth/me');
    return res.data;
  }

  // Dashboard / Metrics
  async getDashboardMetrics(): Promise<DashboardMetrics> {
    try {
      const [ordersRes, reviewRes, lowStockRes, tasksRes] = await Promise.all([
        this.getOrders({ page_size: 100 }),
        this.getOrders({ status: 'NEEDS_REVIEW', page_size: 100 }),
        this.getProducts({ low_stock_only: true, page_size: 100 }),
        this.getAllTasks({ status: 'PENDING', page_size: 100 }),
      ]);

      const orders = ordersRes.data || [];
      const totalRevenue = orders.reduce((sum, o) => sum + (o.total_amount || 0), 0);
      const activeOrders = orders.filter(
        (o) => !['DELIVERED', 'CANCELLED'].includes(o.status)
      ).length;
      const packagingTasks = (tasksRes.data || []).filter((t) => t.task_type === 'PACKAGING').length;
      const deliveryTasks = (tasksRes.data || []).filter((t) => t.task_type === 'DELIVERY').length;

      return {
        total_orders: ordersRes.meta?.total ?? orders.length,
        active_orders: activeOrders,
        pending_packaging: packagingTasks,
        out_for_delivery: deliveryTasks,
        needs_review_count: reviewRes.meta?.total ?? reviewRes.data?.length ?? 0,
        low_stock_count: lowStockRes.meta?.total ?? lowStockRes.data?.length ?? 0,
        total_revenue: totalRevenue,
      };
    } catch {
      return {
        total_orders: 0,
        active_orders: 0,
        pending_packaging: 0,
        out_for_delivery: 0,
        needs_review_count: 0,
        low_stock_count: 0,
        total_revenue: 0,
      };
    }
  }

  // Orders
  async getOrders(params?: { status?: string; page?: number; page_size?: number }): Promise<{ data: Order[]; meta?: any }> {
    const query = new URLSearchParams();
    if (params?.status) query.append('status', params.status);
    if (params?.page) query.append('page', String(params.page));
    if (params?.page_size) query.append('page_size', String(params.page_size));

    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<Order[]>(`/admin/orders${qs}`);
  }

  async getOrder(id: string): Promise<Order> {
    const res = await this.request<Order>(`/admin/orders/${id}`);
    return res.data;
  }

  async createOrder(data: {
    customer_id: string;
    shipping_address: string;
    items: { product_id: string; quantity: number }[];
  }): Promise<Order> {
    const res = await this.request<Order>('/admin/orders', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return res.data;
  }

  async updateOrderStatus(id: string, new_status: string, reason?: string): Promise<Order> {
    const res = await this.request<Order>(`/admin/orders/${id}/status`, {
      method: 'POST',
      body: JSON.stringify({ new_status, reason }),
    });
    return res.data;
  }

  // Products & Inventory
  async getProducts(params?: { low_stock_only?: boolean; search?: string; page?: number; page_size?: number }): Promise<{ data: Product[]; meta?: any }> {
    const query = new URLSearchParams();
    if (params?.low_stock_only) query.append('low_stock_only', 'true');
    if (params?.search) query.append('search', params.search);
    if (params?.page) query.append('page', String(params.page));
    if (params?.page_size) query.append('page_size', String(params.page_size));

    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<Product[]>(`/admin/products${qs}`);
  }

  async createProduct(data: {
    sku: string;
    name: string;
    description?: string;
    price: number;
    initial_stock: number;
    reorder_level?: number;
  }): Promise<Product> {
    const res = await this.request<Product>('/admin/products', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return res.data;
  }

  async adjustStock(
    productId: string,
    data: { delta_qty: number; movement_type: string; reason: string }
  ): Promise<any> {
    const res = await this.request(`/admin/products/${productId}/inventory/adjust`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return res.data;
  }

  async getProductMovements(productId: string): Promise<InventoryMovement[]> {
    const res = await this.request<InventoryMovement[]>(`/admin/products/${productId}/inventory/movements`);
    return res.data;
  }

  // Employees & Tasks
  async getEmployees(): Promise<User[]> {
    const res = await this.request<User[]>('/admin/employees');
    return res.data;
  }

  async createEmployee(data: {
    email: string;
    password: string;
    full_name: string;
    role: string;
  }): Promise<User> {
    const res = await this.request<User>('/admin/employees', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return res.data;
  }

  async getAllTasks(params?: { status?: string; task_type?: string; page?: number; page_size?: number }): Promise<{ data: Task[]; meta?: any }> {
    const query = new URLSearchParams();
    if (params?.status) query.append('status', params.status);
    if (params?.task_type) query.append('task_type', params.task_type);
    if (params?.page) query.append('page', String(params.page));
    if (params?.page_size) query.append('page_size', String(params.page_size));

    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<Task[]>(`/admin/tasks${qs}`);
  }

  async reassignTask(taskId: string, newEmployeeId: string, reason?: string): Promise<Task> {
    const res = await this.request<Task>(`/admin/tasks/${taskId}/reassign`, {
      method: 'POST',
      body: JSON.stringify({ new_employee_id: newEmployeeId, reason }),
    });
    return res.data;
  }

  // Operator Tasks
  async getMyTasks(): Promise<Task[]> {
    const res = await this.request<Task[]>('/employee/tasks/my');
    return res.data;
  }

  async completeTask(taskId: string, payload?: Record<string, any>): Promise<any> {
    const res = await this.request(`/employee/tasks/${taskId}/complete`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    });
    return res.data;
  }

  async reportTaskException(taskId: string, reason: string): Promise<any> {
    const res = await this.request(`/employee/tasks/${taskId}/exception`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
    return res.data;
  }

  // Email Messages & Audit
  async getEmailMessages(params?: {
    direction?: string;
    order_id?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<{ data: EmailMessage[]; meta?: any }> {
    const query = new URLSearchParams();
    if (params?.direction) query.append('direction', params.direction);
    if (params?.order_id) query.append('order_id', params.order_id);
    if (params?.search) query.append('search', params.search);
    if (params?.page) query.append('page', String(params.page));
    if (params?.page_size) query.append('page_size', String(params.page_size));

    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<EmailMessage[]>(`/admin/emails${qs}`);
  }

  async getEmailDetail(id: string): Promise<EmailMessage> {
    const res = await this.request<EmailMessage>(`/admin/emails/${id}`);
    return res.data;
  }

  // Webhook Simulator
  async simulateInboundEmail(payload: {
    message_id?: string;
    sender_email: string;
    sender_name?: string;
    subject: string;
    body_plain: string;
  }): Promise<any> {
    const res = await this.request('/webhooks/email/inbound', {
      method: 'POST',
      body: JSON.stringify({
        message_id: payload.message_id || `<sim_${Date.now()}@client.com>`,
        sender_email: payload.sender_email,
        sender_name: payload.sender_name || 'Inbound Sender',
        subject: payload.subject,
        body_plain: payload.body_plain,
      }),
    });
    return res.data;
  }
}

export const api = new ApiClient();
