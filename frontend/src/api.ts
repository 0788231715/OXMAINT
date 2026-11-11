export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type User = {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_system_admin: boolean;
};

export type Organization = {
  id: string;
  name: string;
  code: string;
  can_register_users: boolean;
};

export type LocationOption = {
  id: string;
  name: string;
  code: string;
};

export type Asset = {
  id: string;
  organization_id: string;
  category_id: string;
  site_id: string;
  department_id: string | null;
  parent_asset_id: string | null;
  asset_tag: string;
  name: string;
  description: string | null;
  manufacturer: string | null;
  serial_number: string | null;
  status: "in_service" | "under_maintenance" | "out_of_service" | "retired";
  criticality: "low" | "medium" | "high" | "critical";
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type AssetCategory = {
  id: string;
  organization_id: string;
  name: string;
  code: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type ServiceRequest = {
  id: string;
  organization_id: string;
  site_id: string;
  department_id: string | null;
  asset_id: string | null;
  requester_id: string;
  request_number: string;
  title: string;
  description: string;
  category: string;
  priority: "low" | "normal" | "high" | "urgent";
  safety_critical: boolean;
  status: string;
  resolution: string | null;
  rejection_reason: string | null;
  cancellation_reason: string | null;
  submitted_at: string;
  created_at: string;
};

export type Page<T> = {
  items: T[];
  total: number;
  offset: number;
  limit: number;
  has_more?: boolean;
};

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

const apiBase = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");

async function request<T>(path: string, token?: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${apiBase}${path}`, { ...init, headers });
  const payload = response.status === 204 ? undefined : await response.json().catch(() => undefined);

  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload
      ? (payload as { detail: unknown }).detail
      : undefined;
    const message = typeof detail === "string" ? detail : `Request failed (${response.status}).`;
    if (response.status === 401 && token) sessionStorage.removeItem("oxmaint-token");
    throw new ApiError(message, response.status);
  }

  return payload as T;
}

function query(values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value));
  });
  return params.toString();
}

export const api = {
  async login(email: string, password: string): Promise<TokenResponse> {
    const form = new URLSearchParams({ username: email, password });
    return request<TokenResponse>("/auth/login", undefined, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form
    });
  },
  me: (token: string) => request<User>("/auth/me", token),
  organizations: (token: string) => request<Organization[]>("/auth/organizations", token),
  sites: (token: string, organizationId: string) => request<LocationOption[]>(`/organizations/${organizationId}/sites`, token),
  departments: (token: string, organizationId: string) => request<LocationOption[]>(`/organizations/${organizationId}/departments`, token),
  assets: (token: string, organizationId: string, options: { offset?: number; limit?: number; search?: string; status?: string } = {}) =>
    request<Page<Asset>>(`/assets?${query({ organization_id: organizationId, ...options })}`, token),
  categories: (token: string, organizationId: string, options: { offset?: number; limit?: number } = {}) =>
    request<Page<AssetCategory>>(`/asset-categories?${query({ organization_id: organizationId, ...options })}`, token),
  createCategory: (token: string, organizationId: string, body: Record<string, unknown>) =>
    request<AssetCategory>(`/asset-categories?organization_id=${encodeURIComponent(organizationId)}`, token, { method: "POST", body: JSON.stringify({ ...body, organization_id: organizationId }) }),
  createAsset: (token: string, organizationId: string, body: Record<string, unknown>) =>
    request<Asset>(`/assets?organization_id=${encodeURIComponent(organizationId)}`, token, { method: "POST", body: JSON.stringify({ ...body, organization_id: organizationId }) }),
  serviceRequests: (token: string, organizationId: string, options: { offset?: number; limit?: number; search?: string; request_status?: string } = {}) =>
    request<Page<ServiceRequest>>(`/service-requests?${query({ organization_id: organizationId, ...options })}`, token),
  createServiceRequest: (token: string, organizationId: string, body: Record<string, unknown>) =>
    request<ServiceRequest>(`/service-requests?organization_id=${encodeURIComponent(organizationId)}`, token, { method: "POST", body: JSON.stringify({ ...body, organization_id: organizationId }) }),
  registerTechnician: (token: string, organizationId: string, body: Record<string, unknown>) =>
    request<{ id: string; email: string; display_name: string; role_code: string; organization_id: string }>(`/users?organization_id=${encodeURIComponent(organizationId)}`, token, { method: "POST", body: JSON.stringify(body) }),
  requestAction: <T,>(token: string, organizationId: string, requestId: string, action: string, body: Record<string, unknown> = {}) =>
    request<T>(`/service-requests/${requestId}/${action}?organization_id=${encodeURIComponent(organizationId)}`, token, { method: "POST", body: JSON.stringify(body) })
};