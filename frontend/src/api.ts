import {
  cacheResponse,
  clearCachedResponses,
  enqueueOperation,
  getLastSync,
  listOperations,
  markOperationConflict,
  readCachedResponse,
  removeOperation,
  retryOperation,
  setLastSync,
  type LocalSyncOperation,
  type OfflineOperationType,
} from "./offlineStore";

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
  description: string | null;
  can_register_users: boolean;
  can_update: boolean;
};

export type OrganizationProfileUpdate = Pick<Organization, "name" | "code" | "description">;

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

export type IncidentSeverity = "low" | "medium" | "high" | "critical";
export type IncidentStatus = "reported" | "investigating" | "resolved" | "closed";
export type IncidentCategory =
  | "safety"
  | "near_miss"
  | "equipment_damage"
  | "environmental"
  | "security"
  | "other";

export type Incident = {
  id: string;
  organization_id: string;
  site_id: string;
  department_id: string | null;
  asset_id: string | null;
  reported_by: string;
  incident_number: string;
  title: string;
  description: string;
  category: IncidentCategory;
  severity: IncidentSeverity;
  status: IncidentStatus;
  occurred_at: string;
  resolution: string | null;
  created_at: string;
  updated_at: string;
};

export type MaintenanceWorkOrderType = "preventive" | "corrective";
export type MaintenanceWorkOrderPriority = "low" | "normal" | "high" | "urgent";
export type MaintenanceWorkOrderStatus =
  | "scheduled"
  | "in_progress"
  | "waiting"
  | "completed"
  | "cancelled";

export type MaintenanceWorkOrder = {
  id: string;
  organization_id: string;
  asset_id: string;
  site_id: string;
  department_id: string | null;
  created_by: string;
  work_order_number: string;
  title: string;
  description: string;
  work_order_type: MaintenanceWorkOrderType;
  priority: MaintenanceWorkOrderPriority;
  status: MaintenanceWorkOrderStatus;
  scheduled_at: string;
  completion_note: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkOrderAssignment = {
  id: string;
  work_order_id: string;
  assigned_to: string;
  assigned_by: string;
  assignee_name: string;
  assigner_name: string;
  handoff_note: string | null;
  assigned_at: string;
};

export type CoordinationWorkOrder = {
  work_order: MaintenanceWorkOrder;
  current_assignment: WorkOrderAssignment | null;
};

export type CoordinationTechnician = {
  id: string;
  display_name: string;
  email: string;
};

export type ReportCount = {
  label: string;
  count: number;
};

export type ReportDailyTrend = {
  date: string;
  requests: number;
  incidents: number;
  work_orders: number;
};

export type ReportsSnapshot = {
  generated_at: string;
  start_date: string;
  end_date: string;
  site_id: string | null;
  summary: {
    assets: number;
    requests: number;
    open_requests: number;
    incidents: number;
    open_incidents: number;
    work_orders: number;
    completed_work_orders: number;
  };
  asset_status: ReportCount[];
  request_status: ReportCount[];
  incident_severity: ReportCount[];
  work_order_status: ReportCount[];
  daily_trend: ReportDailyTrend[];
};

export type AIInsight = {
  title: string;
  category: "assets" | "service_requests" | "safety" | "maintenance";
  severity: "info" | "attention" | "urgent";
  evidence: string[];
  recommendation: string;
};

export type GeneratedAIInsights = {
  generated_at: string;
  start_date: string;
  end_date: string;
  site_id: string | null;
  model: string;
  insights: AIInsight[];
};

export type OperationsMapSite = {
  site_id: string;
  name: string;
  code: string;
  address: string | null;
  assets: number;
  asset_status: Record<string, number>;
  open_requests: number;
  open_incidents: number;
  high_severity_incidents: number;
  open_work_orders: number;
  overdue_work_orders: number;
};

export type OperationsMapSnapshot = {
  generated_at: string;
  summary: {
    sites: number;
    assets: number;
    open_requests: number;
    open_incidents: number;
    overdue_work_orders: number;
  };
  sites: OperationsMapSite[];
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
let offlineUserId = "";

export type OfflineQueuedResult = {
  queued: true;
  operation_id: string;
};

export type OfflineMutationResult = OfflineQueuedResult | {
  queued: false;
  record_id: string;
};

type SyncOperationReceipt = {
  operation_id: string;
  status: "synced";
  duplicate: boolean;
  result: { record_id: string };
};

type SyncSummary = {
  synced: number;
  conflicts: number;
};

async function request<T>(path: string, token?: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, { ...init, headers });
  } catch (error) {
    const cacheContext = getCacheContext(path, init.method);
    if (error instanceof TypeError && cacheContext && offlineUserId) {
      const cached = await readCachedResponse<T>(
        offlineUserId,
        cacheContext.organizationId,
        cacheContext.path
      );
      if (cached !== undefined) return cached;
    }
    throw error;
  }
  const payload = response.status === 204 ? undefined : await response.json().catch(() => undefined);

  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload
      ? (payload as { detail: unknown }).detail
      : undefined;
    const message = typeof detail === "string" ? detail : `Request failed (${response.status}).`;
    if (response.status === 401 && token) sessionStorage.removeItem("oxmaint-token");
    throw new ApiError(message, response.status);
  }

  const cacheContext = getCacheContext(path, init.method);
  if (cacheContext && offlineUserId) {
    await cacheResponse(
      offlineUserId,
      cacheContext.organizationId,
      cacheContext.path,
      payload
    );
  }
  return payload as T;
}

function getCacheContext(
  path: string,
  method: string | undefined
): { organizationId: string; path: string } | undefined {
  if (method && method.toUpperCase() !== "GET") return undefined;
  const url = new URL(`${apiBase}${path}`, window.location.origin);
  const apiPath = new URL(apiBase, window.location.origin).pathname.replace(/\/$/, "");
  const pathname = url.pathname.slice(apiPath.length);
  const cacheable = pathname === "/assets"
    || pathname === "/incidents"
    || pathname === "/service-requests"
    || pathname === "/maintenance/work-orders"
    || /^\/organizations\/[^/]+\/(sites|departments)$/.test(pathname);
  const organizationId = url.searchParams.get("organization_id")
    || pathname.match(/^\/organizations\/([^/]+)\//)?.[1];
  if (!cacheable || !organizationId) return undefined;
  return { organizationId, path: `${url.pathname}${url.search}` };
}

function isNetworkError(error: unknown): boolean {
  return error instanceof TypeError;
}

function notifyQueueChanged() {
  window.dispatchEvent(new Event("oxmaint-sync-queue-updated"));
}

async function pushOperation(
  token: string,
  operation: LocalSyncOperation
): Promise<SyncOperationReceipt> {
  const { operation_id, organization_id, operation_type, record_id, created_at, payload } = operation;
  return request<SyncOperationReceipt>(
    `/synchronization/operations?organization_id=${encodeURIComponent(organization_id)}`,
    token,
    {
      method: "POST",
      body: JSON.stringify({
        operation_id,
        organization_id,
        operation_type,
        record_id,
        created_at,
        payload,
      }),
    }
  );
}

async function enqueueAndSync(
  token: string,
  organizationId: string,
  operationType: OfflineOperationType,
  payload: Record<string, unknown>,
  recordId?: string
): Promise<OfflineMutationResult> {
  if (!offlineUserId) {
    throw new Error("Offline sync requires an authenticated user.");
  }
  const operation = await enqueueOperation(
    offlineUserId,
    organizationId,
    operationType,
    payload,
    recordId
  );
  notifyQueueChanged();
  if (!navigator.onLine) {
    return { queued: true, operation_id: operation.operation_id };
  }

  try {
    const receipt = await pushOperation(token, operation);
    await setLastSync(offlineUserId, organizationId, new Date().toISOString());
    await removeOperation(operation.operation_id);
    notifyQueueChanged();
    return { queued: false, record_id: receipt.result.record_id };
  } catch (error) {
    if (isNetworkError(error)) {
      return { queued: true, operation_id: operation.operation_id };
    }
    if (error instanceof ApiError) {
      await removeOperation(operation.operation_id);
      notifyQueueChanged();
    }
    throw error;
  }
}

async function syncPendingOperations(
  token: string,
  userId: string,
  organizationId: string
): Promise<SyncSummary> {
  const operations = await listOperations(userId, organizationId);
  let synced = 0;
  let conflicts = 0;
  for (const operation of operations) {
    if (operation.state === "conflict") continue;
    try {
      await pushOperation(token, operation);
      await setLastSync(userId, organizationId, new Date().toISOString());
      await removeOperation(operation.operation_id);
      synced += 1;
    } catch (error) {
      if (error instanceof ApiError && [403, 404, 409, 422].includes(error.status)) {
        await markOperationConflict(operation.operation_id, error.message);
        conflicts += 1;
        continue;
      }
      throw error;
    }
  }
  notifyQueueChanged();
  return { synced, conflicts };
}

function query(values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value));
  });
  return params.toString();
}

export const api = {
  setOfflineUser: (userId: string | null) => {
    offlineUserId = userId || "";
  },
  isOnline: () => navigator.onLine,
  offlineOperations: listOperations,
  lastSync: getLastSync,
  clearOfflineCache: clearCachedResponses,
  retryOfflineOperation: retryOperation,
  discardOfflineOperation: removeOperation,
  syncPendingOperations,
  isQueuedResult: (result: unknown): result is OfflineQueuedResult =>
    Boolean(result && typeof result === "object" && "queued" in result && result.queued === true),
  async login(email: string, password: string): Promise<TokenResponse> {
    const form = new URLSearchParams({ username: email, password });
    return request<TokenResponse>("/auth/login", undefined, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form
    });
  },
  me: (token: string) => request<User>("/auth/me", token),
  updateProfile: (token: string, body: Pick<User, "display_name">) =>
    request<User>("/auth/me", token, { method: "PATCH", body: JSON.stringify(body) }),
  organizations: (token: string) => request<Organization[]>("/auth/organizations", token),
  updateOrganization: (token: string, organizationId: string, body: OrganizationProfileUpdate) =>
    request<Organization>(`/organizations?organization_id=${encodeURIComponent(organizationId)}`, token, { method: "PUT", body: JSON.stringify(body) }),
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
  incidents: (token: string, organizationId: string, options: { offset?: number; limit?: number; search?: string; status?: IncidentStatus; severity?: IncidentSeverity } = {}) =>
    request<Page<Incident>>(`/incidents?${query({ organization_id: organizationId, ...options })}`, token),
  createIncident: (token: string, organizationId: string, body: Record<string, unknown>) =>
    enqueueAndSync(
      token,
      organizationId,
      "incident.create",
      { ...body, organization_id: organizationId }
    ),
  updateIncident: (token: string, organizationId: string, incidentId: string, body: Record<string, unknown>) =>
    enqueueAndSync(
      token,
      organizationId,
      "incident.update",
      body,
      incidentId
    ),
  maintenanceWorkOrders: (token: string, organizationId: string, options: { offset?: number; limit?: number; search?: string; status?: MaintenanceWorkOrderStatus; type?: MaintenanceWorkOrderType } = {}) =>
    request<Page<MaintenanceWorkOrder>>(`/maintenance/work-orders?${query({ organization_id: organizationId, ...options })}`, token),
  createMaintenanceWorkOrder: (token: string, organizationId: string, body: Record<string, unknown>) =>
    enqueueAndSync(
      token,
      organizationId,
      "maintenance_work_order.create",
      { ...body, organization_id: organizationId }
    ),
  transitionMaintenanceWorkOrder: (token: string, organizationId: string, workOrderId: string, body: Record<string, unknown>) =>
    enqueueAndSync(
      token,
      organizationId,
      "maintenance_work_order.transition",
      body,
      workOrderId
    ),
  coordinationWorkOrders: (token: string, organizationId: string, options: { offset?: number; limit?: number; search?: string; status?: MaintenanceWorkOrderStatus } = {}) =>
    request<Page<CoordinationWorkOrder>>(`/coordination/work-orders?${query({ organization_id: organizationId, ...options })}`, token),
  coordinationTechnicians: (token: string, organizationId: string, workOrderId: string) =>
    request<CoordinationTechnician[]>(`/coordination/work-orders/${workOrderId}/technicians?organization_id=${encodeURIComponent(organizationId)}`, token),
  coordinationAssignmentHistory: (token: string, organizationId: string, workOrderId: string) =>
    request<{ items: WorkOrderAssignment[] }>(`/coordination/work-orders/${workOrderId}/history?organization_id=${encodeURIComponent(organizationId)}`, token),
  assignCoordinationWorkOrder: (token: string, organizationId: string, workOrderId: string, body: { assigned_to: string; handoff_note?: string }) =>
    request<WorkOrderAssignment>(`/coordination/work-orders/${workOrderId}/assign?organization_id=${encodeURIComponent(organizationId)}`, token, { method: "POST", body: JSON.stringify(body) }),
  reports: (token: string, organizationId: string, options: { start_date: string; end_date: string; site_id?: string }) =>
    request<ReportsSnapshot>(`/reports?${query({ organization_id: organizationId, ...options })}`, token),
  generateAIInsights: (token: string, organizationId: string, body: { start_date: string; end_date: string; site_id?: string; confirm_external_processing: true }) =>
    request<GeneratedAIInsights>(`/ai-insights/generate?organization_id=${encodeURIComponent(organizationId)}`, token, { method: "POST", body: JSON.stringify(body) }),
  operationsMap: (token: string, organizationId: string) =>
    request<OperationsMapSnapshot>(`/operations-map?organization_id=${encodeURIComponent(organizationId)}`, token),
  createServiceRequest: (token: string, organizationId: string, body: Record<string, unknown>) =>
    enqueueAndSync(
      token,
      organizationId,
      "service_request.create",
      { ...body, organization_id: organizationId }
    ),
  registerTechnician: (token: string, organizationId: string, body: Record<string, unknown>) =>
    request<{ id: string; email: string; display_name: string; role_code: string; organization_id: string }>(`/users?organization_id=${encodeURIComponent(organizationId)}`, token, { method: "POST", body: JSON.stringify(body) }),
  requestAction: <T,>(token: string, organizationId: string, requestId: string, action: string, body: Record<string, unknown> = {}) =>
    action === "transition"
      ? enqueueAndSync(
        token,
        organizationId,
        "service_request.transition",
        body,
        requestId
      )
      : request<T>(`/service-requests/${requestId}/${action}?organization_id=${encodeURIComponent(organizationId)}`, token, { method: "POST", body: JSON.stringify(body) })
};