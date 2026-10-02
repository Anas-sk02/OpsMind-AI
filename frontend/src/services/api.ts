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
      let errorMsg = json?.error?.message || json?.detail || `Request failed with status ${response.status}`;
      if (json?.error?.details && Array.isArray(json.error.details) && json.error.details.length > 0) {
        const fieldErrors = json.error.details.map((d: any) => d.message || d.msg).filter(Boolean);
        if (fieldErrors.length > 0) {
          errorMsg = fieldErrors.join(' • ');
        }
      }
      throw new Error(errorMsg);
    }

    return json;
  }

  // Auth Endpoints
  async login(email: string, password: string): Promise<{ access_token: string; refresh_token?: string; user: User }> {
    try {
      const response = await fetch(`${BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      });

      const json = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 401) {
          throw new Error(json?.error?.message || 'Incorrect email or password. Please verify your credentials.');
        }
        if (response.status === 422) {
          const details = json?.error?.details || json?.detail;
          if (Array.isArray(details) && details.length > 0) {
            const detailMsg = details.map((d: any) => d.message || d.msg).filter(Boolean).join(', ');
            throw new Error(`Validation Error: ${detailMsg || 'Please enter a valid email and password format.'}`);
          }
          throw new Error(json?.error?.message || 'Please provide a valid work email and password.');
        }
        if (response.status === 403) {
          throw new Error(json?.error?.message || 'Account access restricted. Please contact your system administrator.');
        }
        throw new Error(json?.error?.message || json?.detail || `Authentication failed (Status ${response.status})`);
      }

      const tokenData = json.data || json;
      this.setToken(tokenData.access_token);
      return tokenData;
    } catch (err: any) {
      if (err.name === 'TypeError' && err.message?.includes('fetch')) {
        throw new Error('Unable to connect to OpsMind server. Please verify your network connection.');
      }
      throw err;
    }
  }

  async getMe(): Promise<User> {
    const res = await this.request<User>('/auth/me');
    return res.data;
  }

  // Dashboard / Metrics
  async getDashboardMetrics(): Promise<DashboardMetrics> {
    try {
      const res = await this.request<DashboardMetrics>('/admin/orders/metrics/summary');
      return res.data;
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
      method: 'PATCH',
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

  async getEmployeeWorkloadMetrics(): Promise<any[]> {
    const res = await this.request<any[]>('/admin/tasks/workload-metrics');
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

  async getTaskDetails(taskId: string): Promise<Task> {
    const res = await this.request<Task>(`/employee/tasks/${taskId}`);
    return res.data;
  }

  async startTask(taskId: string): Promise<any> {
    const res = await this.request(`/employee/tasks/${taskId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ new_status: 'IN_PROGRESS' }),
    });
    return res.data;
  }

  async completeTask(taskId: string, payload?: Record<string, any>): Promise<any> {
    const res = await this.request(`/employee/tasks/${taskId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({
        new_status: 'COMPLETED',
        exception_notes: payload?.notes || null,
      }),
    });
    return res.data;
  }

  async reportTaskException(taskId: string, reason: string): Promise<any> {
    const res = await this.request(`/employee/tasks/${taskId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ new_status: 'EXCEPTION', exception_notes: reason }),
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

  async pollMailboxNow(): Promise<{ polled: boolean; count: number; message: string; processed_orders: any[] }> {
    const res = await this.request<any>('/admin/emails/poll-now', {
      method: 'POST',
    });
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
