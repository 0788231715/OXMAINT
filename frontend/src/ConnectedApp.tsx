import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import type { LocalSyncOperation } from "./offlineStore";
import {
  AlertTriangle, ArrowUpRight, BarChart3, Building2, CheckCircle2,
  ChevronDown, CircleHelp, ClipboardList, Home, LoaderCircle, Menu,
  Moon, Package, Plus, RefreshCw, Search, Settings, Shield, Sun,
  Truck, Users, Wrench, X
} from "lucide-react";
import { api, ApiError, type AIInsight, type GeneratedAIInsights, type Asset, type AssetCategory, type CoordinationTechnician, type CoordinationWorkOrder, type Incident, type IncidentSeverity, type IncidentStatus, type LocationOption, type MaintenanceWorkOrder, type MaintenanceWorkOrderStatus, type MaintenanceWorkOrderType, type OperationsMapSnapshot, type Organization, type Page, type ReportsSnapshot, type ReportCount, type ServiceRequest, type User, type WorkOrderAssignment } from "./api";

const navItems = [
  ["Dashboard", Home, true],
  ["Service Requests", ClipboardList, true],
  ["Assets & Equipment", Truck, true],
  ["Asset Categories", Package, true],
  ["Incidents", AlertTriangle, true],
  ["Maintenance", Wrench, true],
  ["Coordination", Users, true],
  ["Reports & Analytics", BarChart3, true],
  ["AI Insights", CircleHelp, true],
  ["Operations Map", Building2, true],
  ["Synchronization", RefreshCw, true],
  ["Settings", Settings, true],
  ["Help & Support", CircleHelp, false]
] as const;

const transitions: Record<string, string[]> = {
  assigned: ["in_progress", "waiting", "cancelled"],
  in_progress: ["waiting", "completed", "cancelled"],
  waiting: ["in_progress", "cancelled"],
  completed: ["closed"]
};

const incidentTransitions: Record<IncidentStatus, IncidentStatus[]> = {
  reported: ["investigating", "resolved"],
  investigating: ["resolved"],
  resolved: ["closed"],
  closed: []
};

const workOrderTransitions: Record<MaintenanceWorkOrderStatus, MaintenanceWorkOrderStatus[]> = {
  scheduled: ["in_progress", "cancelled"],
  in_progress: ["waiting", "completed", "cancelled"],
  waiting: ["in_progress", "cancelled"],
  completed: [],
  cancelled: []
};

function message(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function dateInputValue(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function defaultReportFilters() {
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - 29);
  return { start_date: dateInputValue(start), end_date: dateInputValue(end), site_id: "" };
}

function readOfflineSession(): { user: User; organizations: Organization[] } | undefined {
  const savedUser = sessionStorage.getItem("oxmaint-offline-user");
  const savedOrganizations = sessionStorage.getItem("oxmaint-offline-organizations");
  if (!savedUser || !savedOrganizations) return undefined;
  try {
    const user = JSON.parse(savedUser) as User;
    const organizations = JSON.parse(savedOrganizations) as Organization[];
    if (
      typeof user.id !== "string"
      || !Array.isArray(organizations)
      || !organizations.every(item => typeof item.id === "string")
    ) {
      return undefined;
    }
    return { user, organizations };
  } catch {
    return undefined;
  }
}

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("oxmaint-token") || "");
  const [user, setUser] = useState<User | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [authLoading, setAuthLoading] = useState(Boolean(sessionStorage.getItem("oxmaint-token")));
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [active, setActive] = useState("Dashboard");
  const [query, setQuery] = useState("");
  const [assetPage, setAssetPage] = useState<Page<Asset> | null>(null);
  const [categoryPage, setCategoryPage] = useState<Page<AssetCategory> | null>(null);
  const [requestPage, setRequestPage] = useState<Page<ServiceRequest> | null>(null);
  const [incidentPage, setIncidentPage] = useState<Page<Incident> | null>(null);
  const [incidentLoading, setIncidentLoading] = useState(false);
  const [incidentError, setIncidentError] = useState("");
  const [incidentStatusFilter, setIncidentStatusFilter] = useState<IncidentStatus | "">("");
  const [incidentSeverityFilter, setIncidentSeverityFilter] = useState<IncidentSeverity | "">("");
  const [incidentOffset, setIncidentOffset] = useState(0);
  const [workOrderPage, setWorkOrderPage] = useState<Page<MaintenanceWorkOrder> | null>(null);
  const [workOrderLoading, setWorkOrderLoading] = useState(false);
  const [workOrderError, setWorkOrderError] = useState("");
  const [workOrderStatusFilter, setWorkOrderStatusFilter] = useState<MaintenanceWorkOrderStatus | "">("");
  const [workOrderTypeFilter, setWorkOrderTypeFilter] = useState<MaintenanceWorkOrderType | "">("");
  const [workOrderOffset, setWorkOrderOffset] = useState(0);
  const [coordinationPage, setCoordinationPage] = useState<Page<CoordinationWorkOrder> | null>(null);
  const [coordinationLoading, setCoordinationLoading] = useState(false);
  const [coordinationError, setCoordinationError] = useState("");
  const [coordinationStatusFilter, setCoordinationStatusFilter] = useState<MaintenanceWorkOrderStatus | "">("");
  const [coordinationOffset, setCoordinationOffset] = useState(0);
  const [selectedCoordinationOrder, setSelectedCoordinationOrder] = useState<CoordinationWorkOrder | null>(null);
  const [coordinationTechnicians, setCoordinationTechnicians] = useState<CoordinationTechnician[]>([]);
  const [coordinationHistory, setCoordinationHistory] = useState<WorkOrderAssignment[]>([]);
  const [coordinationModalLoading, setCoordinationModalLoading] = useState(false);
  const [coordinationModalError, setCoordinationModalError] = useState("");
  const [reportFilters, setReportFilters] = useState(defaultReportFilters);
  const [appliedReportFilters, setAppliedReportFilters] = useState(reportFilters);
  const [reportsSnapshot, setReportsSnapshot] = useState<ReportsSnapshot | null>(null);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [reportsError, setReportsError] = useState("");
  const [aiFilters, setAiFilters] = useState(defaultReportFilters);
  const [aiExternalConsent, setAiExternalConsent] = useState(false);
  const [aiInsights, setAiInsights] = useState<GeneratedAIInsights | null>(null);
  const [aiInsightsLoading, setAiInsightsLoading] = useState(false);
  const [aiInsightsError, setAiInsightsError] = useState("");
  const [operationsMap, setOperationsMap] = useState<OperationsMapSnapshot | null>(null);
  const [operationsMapLoading, setOperationsMapLoading] = useState(false);
  const [operationsMapError, setOperationsMapError] = useState("");
  const [operationsMapOrganizationId, setOperationsMapOrganizationId] = useState("");
  const [isOnline, setIsOnline] = useState(() => api.isOnline());
  const [syncOperations, setSyncOperations] = useState<LocalSyncOperation[]>([]);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncError, setSyncError] = useState("");
  const [lastSyncAt, setLastSyncAt] = useState<string | undefined>();
  const [assetOptions, setAssetOptions] = useState<Asset[]>([]);
  const [assetOptionsLoading, setAssetOptionsLoading] = useState(false);
  const [assetOptionsError, setAssetOptionsError] = useState("");
  const [sites, setSites] = useState<LocationOption[]>([]);
  const [departments, setDepartments] = useState<LocationOption[]>([]);
  const [counts, setCounts] = useState({ inService: 0, maintenance: 0, outOfService: 0, retired: 0, submitted: 0, underReview: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem("oxmaint-theme") === "dark");
  const [settingsError, setSettingsError] = useState("");
  const [settingsNotice, setSettingsNotice] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [organizationSaving, setOrganizationSaving] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [modal, setModal] = useState("");
  const [actionRequest, setActionRequest] = useState<ServiceRequest | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [selectedWorkOrder, setSelectedWorkOrder] = useState<MaintenanceWorkOrder | null>(null);
  const [workOrderStatus, setWorkOrderStatus] = useState<MaintenanceWorkOrderStatus>("scheduled");
  const [actionKind, setActionKind] = useState("");
  const [actionValue, setActionValue] = useState("");
  const [actionUser, setActionUser] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!import.meta.env.PROD) return;
    if (!("serviceWorker" in navigator)) {
      setSyncError("This browser does not support offline app installation.");
      return;
    }
    navigator.serviceWorker.register("/sw.js").catch(error => {
      setSyncError(`Offline app shell could not be cached: ${message(error)}`);
    });
  }, []);

  useEffect(() => {
    localStorage.setItem("oxmaint-theme", dark ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    if (!token) {
      setAuthLoading(false);
      return;
    }
    let current = true;
    setAuthLoading(true);
    Promise.all([api.me(token), api.organizations(token)]).then(([profile, orgs]) => {
      if (!current) return;
      setUser(profile);
      setOrganizations(orgs);
      api.setOfflineUser(profile.id);
      sessionStorage.setItem("oxmaint-offline-user", JSON.stringify(profile));
      sessionStorage.setItem("oxmaint-offline-organizations", JSON.stringify(orgs));
      const savedOrganizationId = sessionStorage.getItem("oxmaint-organization-id") || "";
      setOrganizationId(selected => {
        const selectedOrganization = orgs.some(org => org.id === selected)
          ? selected
          : orgs.some(org => org.id === savedOrganizationId)
            ? savedOrganizationId
            : orgs[0]?.id || "";
        return selectedOrganization;
      });
    }).catch(err => {
      if (!current) return;
      const cachedSession = err instanceof TypeError ? readOfflineSession() : undefined;
      if (cachedSession) {
        setUser(cachedSession.user);
        setOrganizations(cachedSession.organizations);
        api.setOfflineUser(cachedSession.user.id);
        const savedOrganizationId = sessionStorage.getItem("oxmaint-organization-id") || "";
        setOrganizationId(
          cachedSession.organizations.some(org => org.id === savedOrganizationId)
            ? savedOrganizationId
            : cachedSession.organizations[0]?.id || ""
        );
        setNotice("Offline workspace restored. Cached data may be up to 24 hours old.");
      } else {
        setLoginError(
          err instanceof TypeError
            ? "Connect to OxMaint online once before using the workspace offline."
            : message(err)
        );
        sessionStorage.removeItem("oxmaint-token");
        setToken("");
        api.setOfflineUser(null);
      }
    }).finally(() => current && setAuthLoading(false));
    return () => { current = false; };
  }, [token]);

  useEffect(() => {
    if (organizationId) sessionStorage.setItem("oxmaint-organization-id", organizationId);
  }, [organizationId]);

  useEffect(() => {
    setIsOnline(api.isOnline());
    if (!token || !user || !organizationId) {
      setSyncOperations([]);
      setLastSyncAt(undefined);
      setSyncLoading(false);
      return;
    }

    let current = true;
    let synchronizationRunning = false;
    const refreshQueue = async () => {
      try {
        const [operations, lastSync] = await Promise.all([
          api.offlineOperations(user.id, organizationId),
          api.lastSync(user.id, organizationId),
        ]);
        if (current) {
          setSyncOperations(operations);
          setLastSyncAt(lastSync);
        }
      } catch (error) {
        if (current) setSyncError(message(error));
      }
    };
    const synchronize = async () => {
      setIsOnline(api.isOnline());
      if (!api.isOnline() || synchronizationRunning) {
        await refreshQueue();
        return;
      }
      synchronizationRunning = true;
      setSyncLoading(true);
      setSyncError("");
      try {
        const result = await api.syncPendingOperations(token, user.id, organizationId);
        if (current && result.synced > 0) {
          setReload(value => value + 1);
          setNotice(`${result.synced} offline change${result.synced === 1 ? "" : "s"} synchronized.`);
        }
      } catch (error) {
        if (current) {
          setSyncError(message(error));
          if (error instanceof ApiError && error.status === 401) {
            sessionStorage.removeItem("oxmaint-token");
            setToken("");
            setUser(null);
            api.setOfflineUser(null);
          }
        }
      } finally {
        synchronizationRunning = false;
        if (current) setSyncLoading(false);
        await refreshQueue();
      }
    };
    const handleOnline = () => {
      setIsOnline(true);
      void synchronize();
    };
    const handleOffline = () => setIsOnline(false);
    const handleQueueChanged = () => { void refreshQueue(); };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    window.addEventListener("oxmaint-sync-queue-updated", handleQueueChanged);
    void synchronize();
    return () => {
      current = false;
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("oxmaint-sync-queue-updated", handleQueueChanged);
    };
  }, [token, user?.id, organizationId]);

  useEffect(() => {
    if (!token || !organizationId) return;
    let current = true;
    setLoading(true);
    setError("");
    Promise.allSettled([
      api.assets(token, organizationId, { limit: 100, search: query || undefined }),
      api.categories(token, organizationId, { limit: 100 }),
      api.serviceRequests(token, organizationId, { limit: 100, search: query || undefined }),
      api.sites(token, organizationId),
      api.departments(token, organizationId),
      api.assets(token, organizationId, { limit: 1, status: "under_maintenance" }),
      api.assets(token, organizationId, { limit: 1, status: "out_of_service" }),
      api.assets(token, organizationId, { limit: 1, status: "in_service" }),
      api.assets(token, organizationId, { limit: 1, status: "retired" }),
      api.serviceRequests(token, organizationId, { limit: 1, request_status: "submitted" }),
      api.serviceRequests(token, organizationId, { limit: 1, request_status: "under_review" })
    ]).then(results => {
      if (!current) return;
      const [assets, categories, requests, accessibleSites, accessibleDepartments, maintenance, outOfService, inService, retired, submitted, underReview] = results;
      if (assets.status === "fulfilled") setAssetPage(assets.value);
      if (categories.status === "fulfilled") setCategoryPage(categories.value);
      if (requests.status === "fulfilled") setRequestPage(requests.value);
      if (accessibleSites.status === "fulfilled") setSites(accessibleSites.value);
      if (accessibleDepartments.status === "fulfilled") setDepartments(accessibleDepartments.value);
      setCounts({
        inService: inService.status === "fulfilled" ? inService.value.total : 0,
        maintenance: maintenance.status === "fulfilled" ? maintenance.value.total : 0,
        outOfService: outOfService.status === "fulfilled" ? outOfService.value.total : 0,
        retired: retired.status === "fulfilled" ? retired.value.total : 0,
        submitted: submitted.status === "fulfilled" ? submitted.value.total : 0,
        underReview: underReview.status === "fulfilled" ? underReview.value.total : 0
      });
      const failures = results.filter(result => result.status === "rejected");
      if (failures.length === results.length) {
        const first = failures[0];
        setError(first?.status === "rejected" ? message(first.reason) : "Could not load workspace data.");
      } else if (failures.length) {
        setError("Some data is unavailable for your permissions. Other loaded sections remain usable.");
      }
      const expired = failures.find(result => result.status === "rejected" && result.reason instanceof ApiError && result.reason.status === 401);
      if (expired) {
        sessionStorage.removeItem("oxmaint-token");
        setToken("");
        setUser(null);
      }
      setLoading(false);
    });
    return () => { current = false; };
  }, [token, organizationId, reload, query]);

  useEffect(() => {
    if (!token || !organizationId) {
      setIncidentPage(null);
      setIncidentLoading(false);
      return;
    }

    let current = true;
    setIncidentLoading(true);
    setIncidentError("");
    api.incidents(token, organizationId, {
      offset: incidentOffset,
      limit: 25,
      search: query || undefined,
      status: incidentStatusFilter || undefined,
      severity: incidentSeverityFilter || undefined
    }).then(page => {
      if (current) setIncidentPage(page);
    }).catch(err => {
      if (!current) return;
      setIncidentError(message(err));
      if (err instanceof ApiError && err.status === 401) {
        sessionStorage.removeItem("oxmaint-token");
        setToken("");
        setUser(null);
      }
    }).finally(() => current && setIncidentLoading(false));

    return () => { current = false; };
  }, [token, organizationId, reload, query, incidentOffset, incidentStatusFilter, incidentSeverityFilter]);

  useEffect(() => {
    if (!token || !organizationId) {
      setWorkOrderPage(null);
      setWorkOrderLoading(false);
      return;
    }

    let current = true;
    setWorkOrderLoading(true);
    setWorkOrderError("");
    api.maintenanceWorkOrders(token, organizationId, {
      offset: workOrderOffset,
      limit: 25,
      search: query || undefined,
      status: workOrderStatusFilter || undefined,
      type: workOrderTypeFilter || undefined
    }).then(page => {
      if (current) setWorkOrderPage(page);
    }).catch(err => {
      if (!current) return;
      setWorkOrderError(message(err));
      if (err instanceof ApiError && err.status === 401) {
        sessionStorage.removeItem("oxmaint-token");
        setToken("");
        setUser(null);
      }
    }).finally(() => current && setWorkOrderLoading(false));

    return () => { current = false; };
  }, [token, organizationId, reload, query, workOrderOffset, workOrderStatusFilter, workOrderTypeFilter]);

  useEffect(() => {
    if (!token || !organizationId) {
      setCoordinationPage(null);
      setCoordinationLoading(false);
      return;
    }

    let current = true;
    setCoordinationLoading(true);
    setCoordinationError("");
    api.coordinationWorkOrders(token, organizationId, {
      offset: coordinationOffset,
      limit: 25,
      search: query || undefined,
      status: coordinationStatusFilter || undefined
    }).then(page => {
      if (current) setCoordinationPage(page);
    }).catch(err => {
      if (!current) return;
      setCoordinationError(message(err));
      if (err instanceof ApiError && err.status === 401) {
        sessionStorage.removeItem("oxmaint-token");
        setToken("");
        setUser(null);
      }
    }).finally(() => current && setCoordinationLoading(false));

    return () => { current = false; };
  }, [token, organizationId, reload, query, coordinationOffset, coordinationStatusFilter]);

  useEffect(() => {
    if (!token || !organizationId || !selectedCoordinationOrder) {
      setCoordinationTechnicians([]);
      setCoordinationHistory([]);
      setCoordinationModalLoading(false);
      return;
    }

    let current = true;
    setCoordinationModalLoading(true);
    setCoordinationModalError("");
    Promise.all([
      api.coordinationTechnicians(token, organizationId, selectedCoordinationOrder.work_order.id),
      api.coordinationAssignmentHistory(token, organizationId, selectedCoordinationOrder.work_order.id)
    ]).then(([technicians, history]) => {
      if (!current) return;
      setCoordinationTechnicians(technicians);
      setCoordinationHistory(history.items);
    }).catch(err => {
      if (!current) return;
      setCoordinationModalError(message(err));
      if (err instanceof ApiError && err.status === 401) {
        sessionStorage.removeItem("oxmaint-token");
        setToken("");
        setUser(null);
      }
    }).finally(() => current && setCoordinationModalLoading(false));

    return () => { current = false; };
  }, [token, organizationId, selectedCoordinationOrder, reload]);

  useEffect(() => {
    if (!token || !organizationId || active !== "Reports & Analytics") {
      setReportsLoading(false);
      if (!token || !organizationId) setReportsSnapshot(null);
      return;
    }

    let current = true;
    setReportsLoading(true);
    setReportsError("");
    api.reports(token, organizationId, {
      start_date: appliedReportFilters.start_date,
      end_date: appliedReportFilters.end_date,
      site_id: appliedReportFilters.site_id || undefined
    }).then(snapshot => {
      if (current) setReportsSnapshot(snapshot);
    }).catch(err => {
      if (!current) return;
      setReportsError(message(err));
      if (err instanceof ApiError && err.status === 401) {
        sessionStorage.removeItem("oxmaint-token");
        setToken("");
        setUser(null);
      }
    }).finally(() => current && setReportsLoading(false));

    return () => { current = false; };
  }, [token, organizationId, active, appliedReportFilters, reload]);

  useEffect(() => {
    if (!token || !organizationId || active !== "Operations Map") {
      setOperationsMapLoading(false);
      if (!token || !organizationId) {
        setOperationsMap(null);
        setOperationsMapOrganizationId("");
      }
      return;
    }

    let current = true;
    setOperationsMapLoading(true);
    setOperationsMapError("");
    api.operationsMap(token, organizationId).then(snapshot => {
      if (current) {
        setOperationsMap(snapshot);
        setOperationsMapOrganizationId(organizationId);
      }
    }).catch(err => {
      if (!current) return;
      setOperationsMapError(message(err));
      if (err instanceof ApiError && err.status === 401) {
        sessionStorage.removeItem("oxmaint-token");
        setToken("");
        setUser(null);
      }
    }).finally(() => current && setOperationsMapLoading(false));

    return () => { current = false; };
  }, [token, organizationId, active, reload]);

  useEffect(() => {
    if (!token || !organizationId) {
      setAssetOptions([]);
      setAssetOptionsLoading(false);
      return;
    }

    let current = true;
    setAssetOptionsLoading(true);
    setAssetOptionsError("");
    api.assets(token, organizationId, { limit: 100 }).then(page => {
      if (current) setAssetOptions(page.items);
    }).catch(err => {
      if (!current) return;
      setAssetOptionsError(message(err));
      if (err instanceof ApiError && err.status === 401) {
        sessionStorage.removeItem("oxmaint-token");
        setToken("");
        setUser(null);
      }
    }).finally(() => current && setAssetOptionsLoading(false));

    return () => { current = false; };
  }, [token, organizationId, reload]);

  const org = organizations.find(item => item.id === organizationId);
  const assets = useMemo(() => (assetPage?.items || []).filter(item => `${item.asset_tag} ${item.name} ${item.status} ${item.criticality}`.toLowerCase().includes(query.toLowerCase())), [assetPage, query]);
  const requests = useMemo(() => (requestPage?.items || []).filter(item => `${item.request_number} ${item.title} ${item.status} ${item.priority}`.toLowerCase().includes(query.toLowerCase())), [requestPage, query]);

  async function login(email: string, password: string) {
    setLoginLoading(true);
    setLoginError("");
    setSettingsError("");
    setSettingsNotice("");
    try {
      const result = await api.login(email, password);
      sessionStorage.removeItem("oxmaint-offline-user");
      sessionStorage.removeItem("oxmaint-offline-organizations");
      sessionStorage.removeItem("oxmaint-organization-id");
      sessionStorage.setItem("oxmaint-token", result.access_token);
      setToken(result.access_token);
    } catch (err) { setLoginError(message(err)); }
    finally { setLoginLoading(false); }
  }

  function signOut() {
    const offlineOwner = user?.id;
    if (offlineOwner) {
      void api.clearOfflineCache(offlineOwner).catch(err => {
        setLoginError(`Could not clear this user’s cached offline data: ${message(err)}`);
      });
    }
    sessionStorage.removeItem("oxmaint-token");
    sessionStorage.removeItem("oxmaint-offline-user");
    sessionStorage.removeItem("oxmaint-offline-organizations");
    sessionStorage.removeItem("oxmaint-organization-id");
    api.setOfflineUser(null);
    setToken("");
    setUser(null);
    setOrganizations([]);
    setOrganizationId("");
    setAssetPage(null);
    setCategoryPage(null);
    setRequestPage(null);
    setIncidentPage(null);
    setWorkOrderPage(null);
    setCoordinationPage(null);
    setAssetOptions([]);
    setSelectedIncident(null);
    setSelectedWorkOrder(null);
    setSelectedCoordinationOrder(null);
    setReportsSnapshot(null);
    setAiInsights(null);
    setSyncOperations([]);
    setSettingsError("");
    setSettingsNotice("");
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !user) return;
    if (!isOnline) {
      setSettingsError("Connect to the server to update your profile.");
      return;
    }
    const form = new FormData(event.currentTarget);
    setSettingsError("");
    setSettingsNotice("");
    setProfileSaving(true);
    try {
      const updatedUser = await api.updateProfile(token, {
        display_name: String(form.get("display_name") || "")
      });
      setUser(updatedUser);
      sessionStorage.setItem("oxmaint-offline-user", JSON.stringify(updatedUser));
      setSettingsNotice("Your profile was updated.");
    } catch (err) {
      setSettingsError(message(err));
      if (err instanceof ApiError && err.status === 401) {
        sessionStorage.removeItem("oxmaint-token");
        setToken("");
        setUser(null);
        api.setOfflineUser(null);
      }
    } finally {
      setProfileSaving(false);
    }
  }

  async function saveOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !organizationId || !org?.can_update) return;
    if (!isOnline) {
      setSettingsError("Connect to the server to update organization settings.");
      return;
    }
    const form = new FormData(event.currentTarget);
    setSettingsError("");
    setSettingsNotice("");
    setOrganizationSaving(true);
    try {
      const updatedOrganization = await api.updateOrganization(token, organizationId, {
        name: String(form.get("name") || ""),
        code: String(form.get("code") || ""),
        description: String(form.get("description") || "") || null
      });
      const updatedOrganizations = organizations.map(item =>
        item.id === organizationId ? updatedOrganization : item
      );
      setOrganizations(updatedOrganizations);
      sessionStorage.setItem("oxmaint-offline-organizations", JSON.stringify(updatedOrganizations));
      setSettingsNotice("Organization profile was updated.");
    } catch (err) {
      setSettingsError(message(err));
      if (err instanceof ApiError && err.status === 401) {
        sessionStorage.removeItem("oxmaint-token");
        setToken("");
        setUser(null);
        api.setOfflineUser(null);
      }
    } finally {
      setOrganizationSaving(false);
    }
  }

  async function generateAiInsights(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !organizationId) return;
    if (!aiExternalConsent) {
      setAiInsightsError("Confirm external processing before generating insights.");
      return;
    }
    const start = Date.parse(`${aiFilters.start_date}T00:00:00Z`);
    const end = Date.parse(`${aiFilters.end_date}T00:00:00Z`);
    if (!aiFilters.start_date || !aiFilters.end_date || start > end) {
      setAiInsightsError("Choose a valid date range with the start on or before the end.");
      return;
    }
    if ((end - start) / 86400000 > 365) {
      setAiInsightsError("Choose a date range of 366 days or less.");
      return;
    }
    setAiInsights(null);
    setAiInsightsError("");
    setAiExternalConsent(false);
    setAiInsightsLoading(true);
    try {
      const result = await api.generateAIInsights(token, organizationId, {
        start_date: aiFilters.start_date,
        end_date: aiFilters.end_date,
        site_id: aiFilters.site_id || undefined,
        confirm_external_processing: true
      });
      setAiInsights(result);
    } catch (err) {
      setAiInsightsError(message(err));
      if (err instanceof ApiError && err.status === 401) {
        sessionStorage.removeItem("oxmaint-token");
        setToken("");
        setUser(null);
      }
    } finally {
      setAiInsightsLoading(false);
    }
  }

  function applyReportFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reportFilters.start_date || !reportFilters.end_date) {
      setReportsError("Choose both a start date and an end date.");
      return;
    }
    const start = Date.parse(`${reportFilters.start_date}T00:00:00Z`);
    const end = Date.parse(`${reportFilters.end_date}T00:00:00Z`);
    if (start > end) {
      setReportsError("The start date must be on or before the end date.");
      return;
    }
    if ((end - start) / 86400000 > 365) {
      setReportsError("Choose a date range of 366 days or less.");
      return;
    }
    setReportsError("");
    setAppliedReportFilters(reportFilters);
  }

  function downloadReportsCsv() {
    if (!reportsSnapshot) return;
    const rows: (string | number)[][] = [
      ["Section", "Metric", "Count"],
      ["Summary", "Assets in current inventory", reportsSnapshot.summary.assets],
      ["Summary", "Service requests in period", reportsSnapshot.summary.requests],
      ["Summary", "Open service requests in period", reportsSnapshot.summary.open_requests],
      ["Summary", "Incidents in period", reportsSnapshot.summary.incidents],
      ["Summary", "Open incidents in period", reportsSnapshot.summary.open_incidents],
      ["Summary", "Work orders scheduled in period", reportsSnapshot.summary.work_orders],
      ["Summary", "Completed work orders in period", reportsSnapshot.summary.completed_work_orders],
      ...reportsSnapshot.asset_status.map(item => ["Asset status", item.label, item.count]),
      ...reportsSnapshot.request_status.map(item => ["Request status", item.label, item.count]),
      ...reportsSnapshot.incident_severity.map(item => ["Incident severity", item.label, item.count]),
      ...reportsSnapshot.work_order_status.map(item => ["Work order status", item.label, item.count]),
      ...reportsSnapshot.daily_trend.map(item => [`Daily trend ${item.date}`, "Service requests", item.requests]),
      ...reportsSnapshot.daily_trend.map(item => [`Daily trend ${item.date}`, "Incidents", item.incidents]),
      ...reportsSnapshot.daily_trend.map(item => [`Daily trend ${item.date}`, "Work orders", item.work_orders])
    ];
    const csv = rows.map(row => row.map(value => `"${String(value).replaceAll("\"", "\"\"")}"`).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `oxmaint-report-${reportsSnapshot.start_date}-to-${reportsSnapshot.end_date}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  async function submitForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !organizationId) return;
    setSubmitting(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const body: Record<string, unknown> = Object.fromEntries(form.entries());
    let queuedOffline = false;
    try {
      if (modal === "asset") {
        body.department_id = body.department_id || null;
        body.parent_asset_id = null;
        await api.createAsset(token, organizationId, body);
      } else if (modal === "category") {
        await api.createCategory(token, organizationId, body);
      } else if (modal === "request") {
        body.department_id = body.department_id || null;
        body.asset_id = body.asset_id || null;
        body.safety_critical = form.get("safety_critical") === "on";
        const result = await api.createServiceRequest(token, organizationId, body);
        queuedOffline = api.isQueuedResult(result);
      } else if (modal === "incident") {
        body.department_id = body.department_id || null;
        body.asset_id = body.asset_id || null;
        const occurredAt = new Date(String(body.occurred_at));
        if (Number.isNaN(occurredAt.getTime())) throw new Error("Enter a valid incident date and time.");
        body.occurred_at = occurredAt.toISOString();
        const result = await api.createIncident(token, organizationId, body);
        queuedOffline = api.isQueuedResult(result);
      } else if (modal === "workOrder") {
        const scheduledAt = new Date(String(body.scheduled_at));
        if (Number.isNaN(scheduledAt.getTime())) throw new Error("Enter a valid scheduled date and time.");
        body.scheduled_at = scheduledAt.toISOString();
        const result = await api.createMaintenanceWorkOrder(token, organizationId, body);
        queuedOffline = api.isQueuedResult(result);
      } else if (modal === "user") {
        const siteIds = form.getAll("site_ids").map(String);
        if (!siteIds.length) throw new Error("Select at least one site.");
        body.site_ids = siteIds;
        body.department_ids = form.getAll("department_ids").map(String);
        await api.registerTechnician(token, organizationId, body);
      }
      setModal("");
      setNotice(queuedOffline
        ? "Saved on this device. It will sync when a connection is available."
        : modal === "asset" ? "Asset created." : modal === "category" ? "Category created." : modal === "request" ? "Service request submitted." : modal === "incident" ? "Incident reported." : modal === "workOrder" ? "Maintenance work order scheduled." : "Maintenance technician registered.");
      setReload(value => value + 1);
    } catch (err) { setError(message(err)); }
    finally { setSubmitting(false); }
  }

  async function submitIncidentUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedIncident || !token || !organizationId) return;
    const form = new FormData(event.currentTarget);
    const body = Object.fromEntries(form.entries()) as Record<string, unknown>;
    body.resolution = body.resolution || null;
    setSubmitting(true);
    setError("");
    try {
      const result = await api.updateIncident(token, organizationId, selectedIncident.id, body);
      setSelectedIncident(null);
      setNotice(api.isQueuedResult(result)
        ? "Incident update saved on this device and queued for synchronization."
        : "Incident updated.");
      setReload(value => value + 1);
    } catch (err) {
      setError(message(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitWorkOrderTransition(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkOrder || !token || !organizationId) return;
    const form = new FormData(event.currentTarget);
    const body = Object.fromEntries(form.entries()) as Record<string, unknown>;
    body.completion_note = body.completion_note || null;
    setSubmitting(true);
    setError("");
    try {
      const result = await api.transitionMaintenanceWorkOrder(
        token,
        organizationId,
        selectedWorkOrder.id,
        body
      );
      setSelectedWorkOrder(null);
      setNotice(api.isQueuedResult(result)
        ? "Work order update saved on this device and queued for synchronization."
        : "Maintenance work order updated.");
      setReload(value => value + 1);
    } catch (err) {
      setError(message(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitCoordinationAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCoordinationOrder || !token || !organizationId) return;
    const form = new FormData(event.currentTarget);
    const assignedTo = String(form.get("assigned_to") || "");
    if (!assignedTo) {
      setCoordinationModalError("Choose a technician for this work order.");
      return;
    }
    setSubmitting(true);
    setCoordinationModalError("");
    try {
      await api.assignCoordinationWorkOrder(token, organizationId, selectedCoordinationOrder.work_order.id, {
        assigned_to: assignedTo,
        handoff_note: String(form.get("handoff_note") || "").trim() || undefined
      });
      setSelectedCoordinationOrder(null);
      setNotice("Technician assignment and handoff saved.");
      setReload(value => value + 1);
    } catch (err) {
      setCoordinationModalError(message(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitAction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!actionRequest || !token || !organizationId) return;
    let body: Record<string, unknown> = {};
    if (actionKind === "review") body = { review_note: actionValue || null };
    if (actionKind === "approve") body = { decision: "approved", decision_note: actionValue || null };
    if (actionKind === "reject") body = { reason: actionValue };
    if (actionKind === "assign") body = { assigned_to: actionUser, assignment_note: actionValue || null };
    if (actionKind === "transition") body = { new_status: actionValue, reason: actionValue === "cancelled" ? "Cancelled from operations workspace." : null, resolution: actionValue === "completed" ? "Resolved from operations workspace." : null };
    setSubmitting(true);
    try {
      const result = await api.requestAction(token, organizationId, actionRequest.id, actionKind, body);
      setActionRequest(null);
      setNotice(api.isQueuedResult(result)
        ? "Request transition saved on this device and queued for synchronization."
        : `${actionKind[0]?.toUpperCase()}${actionKind.slice(1)} completed.`);
      setReload(value => value + 1);
    } catch (err) { setError(message(err)); }
    finally { setSubmitting(false); }
  }

  async function synchronizeNow() {
    if (!token || !user || !organizationId || !api.isOnline()) return;
    setSyncLoading(true);
    setSyncError("");
    try {
      const result = await api.syncPendingOperations(token, user.id, organizationId);
      if (result.synced > 0) {
        setReload(value => value + 1);
        setNotice(`${result.synced} offline change${result.synced === 1 ? "" : "s"} synchronized.`);
      }
      setSyncOperations(await api.offlineOperations(user.id, organizationId));
      setLastSyncAt(await api.lastSync(user.id, organizationId));
      if (result.conflicts > 0) {
        setSyncError(`${result.conflicts} operation${result.conflicts === 1 ? "" : "s"} need review.`);
      }
    } catch (err) {
      setSyncError(message(err));
    } finally {
      setSyncLoading(false);
    }
  }

  async function retrySynchronizationOperation(operationId: string) {
    if (!user || !organizationId) return;
    try {
      await api.retryOfflineOperation(operationId);
      setSyncOperations(await api.offlineOperations(user.id, organizationId));
      await synchronizeNow();
    } catch (err) {
      setSyncError(message(err));
    }
  }

  async function discardSynchronizationOperation(operationId: string) {
    if (!user || !organizationId) return;
    try {
      await api.discardOfflineOperation(operationId);
      setSyncOperations(await api.offlineOperations(user.id, organizationId));
    } catch (err) {
      setSyncError(message(err));
    }
  }

  if (authLoading) return <div className="full-loading"><LoaderCircle className="spin"/>Loading your workspace</div>;
  if (!token || !user) return <Login onSubmit={login} busy={loginLoading} error={loginError}/>;

  const activeSectionAvailable = navItems.find(item => item[0] === active)?.[2] ?? false;
  const openRequests = counts.submitted + counts.underReview;

  return <div className={`app-shell ${dark ? "dark" : ""}`}>
    <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
      <div className="brand"><div className="brand-mark"><Shield size={27}/></div><div><strong>OxMaint</strong><span>Operations · Support · Resilience</span></div><button className="mobile-close" onClick={() => setSidebarOpen(false)} aria-label="Close navigation"><X size={19}/></button></div>
      <nav className="side-nav" aria-label="Main navigation">{navItems.map(([label, Icon, available]) => <button key={label} className={`nav-item ${active === label ? "active" : ""} ${available ? "" : "nav-unavailable"}`} title={available ? label : `${label} API is not available yet`} onClick={() => { setActive(label); setSidebarOpen(false); }}><Icon size={18}/><span>{label}</span>{!available && <small>Later</small>}</button>)}</nav>
      <div className="system-card"><div className={`system-check ${isOnline ? "" : "offline"}`}><CheckCircle2 size={19}/></div><div><strong>{!isOnline ? "Offline workspace" : loading ? "Refreshing data" : error ? "Connection needs attention" : "Network available"}</strong><span>{org?.name || "Choose an organization"}</span></div></div>
      <div className="theme-switch"><Moon size={16}/><button aria-label="Toggle theme" onClick={() => setDark(!dark)} className={`switch ${dark ? "on" : ""}`}><span/></button><Sun size={16}/></div>
      <div className="sidebar-footer">OxMaint Platform <span>v1.0.0</span></div>
    </aside>
    {sidebarOpen && <button className="scrim" onClick={() => setSidebarOpen(false)} aria-label="Close menu"/>}
    <div className="main-area">
      <header className="topbar">
        <button className="mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="Open menu"><Menu size={21}/></button>
        <div className="search-wrap"><Search size={18}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search assets, requests, incidents, maintenance..."/></div>
        <div className="topbar-right">
          <div className={`online ${isOnline ? "" : "offline"}`}><span/>{isOnline ? "Network online" : "Offline mode"}</div>
          <label className="organization-select"><Building2 size={16}/><select aria-label="Organization" value={organizationId} onChange={event => { setOrganizationId(event.target.value); setIncidentOffset(0); setIncidentPage(null); setSelectedIncident(null); setWorkOrderOffset(0); setWorkOrderPage(null); setSelectedWorkOrder(null); setCoordinationOffset(0); setCoordinationPage(null); setSelectedCoordinationOrder(null); setReportFilters(filters => ({ ...filters, site_id: "" })); setAppliedReportFilters(filters => ({ ...filters, site_id: "" })); setAiFilters(filters => ({ ...filters, site_id: "" })); setAiInsights(null); }}><option value="">No organization</option>{organizations.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select><ChevronDown size={14}/></label>
          <div className="notification-wrap"><button className="icon-button" onClick={() => setNotificationsOpen(!notificationsOpen)} aria-label="Request notifications"><ClipboardList size={19}/><b>{openRequests}</b></button>{notificationsOpen && <div className="notification-popover"><strong>Service requests</strong><p>{counts.submitted} submitted</p><p>{counts.underReview} under review</p></div>}</div>
          <button className="user-menu" onClick={signOut}><span className="user-avatar">{user.display_name.slice(0, 1).toUpperCase()}</span><span><strong>{user.display_name}</strong><small>{user.is_system_admin ? "System Administrator · Sign out" : "Sign out"}</small></span><ChevronDown size={15}/></button>
        </div>
      </header>
      <main className="content">
        <div className="page-heading"><div className="heading-left"><div className="heading-icon"><Shield size={24}/></div><div><h1>{active === "Dashboard" ? "Operations Dashboard" : active}</h1><p>{org ? `${org.name} · ${isOnline ? "Live database data" : "Cached offline data"}` : active === "Settings" ? "Personal account and organization preferences" : "Select an organization"}</p></div></div><div className="heading-tools"><button className="refresh-button" onClick={() => setReload(value => value + 1)} disabled={!isOnline || loading || incidentLoading || workOrderLoading || coordinationLoading} aria-label="Refresh data"><RefreshCw size={17} className={loading || incidentLoading || workOrderLoading || coordinationLoading ? "spin" : ""}/></button>{org?.can_register_users && <button className="secondary-button" onClick={() => setModal("user")}><Users size={15}/>Register user</button>}{active === "Assets & Equipment" && <button className="primary-button" onClick={() => setModal("asset")}><Plus size={16}/>New Asset</button>}{active === "Asset Categories" && <button className="primary-button" onClick={() => setModal("category")}><Plus size={16}/>New Category</button>}{active === "Service Requests" && <button className="primary-button" onClick={() => setModal("request")}><Plus size={16}/>New Request</button>}{active === "Incidents" && <button className="primary-button" onClick={() => setModal("incident")}><Plus size={16}/>Report Incident</button>}{active === "Maintenance" && <button className="primary-button" onClick={() => { setError(""); setModal("workOrder"); }}><Plus size={16}/>Schedule Work</button>}</div></div>
        {notice && <div className="notice"><CheckCircle2 size={16}/>{notice}<button onClick={() => setNotice("")} aria-label="Dismiss"><X size={15}/></button></div>}
        {error && <div className="form-error page-error" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss error"><X size={15}/></button></div>}
        {incidentError && active === "Incidents" && <div className="form-error page-error" role="alert">{incidentError}<button onClick={() => setIncidentError("")} aria-label="Dismiss error"><X size={15}/></button></div>}
        {workOrderError && active === "Maintenance" && <div className="form-error page-error" role="alert">{workOrderError}<button onClick={() => setWorkOrderError("")} aria-label="Dismiss error"><X size={15}/></button></div>}
        {coordinationError && active === "Coordination" && <div className="form-error page-error" role="alert">{coordinationError}<button onClick={() => setCoordinationError("")} aria-label="Dismiss error"><X size={15}/></button></div>}
        {reportsError && active === "Reports & Analytics" && <div className="form-error page-error" role="alert">{reportsError}<button onClick={() => setReportsError("")} aria-label="Dismiss error"><X size={15}/></button></div>}
        {aiInsightsError && active === "AI Insights" && <div className="form-error page-error" role="alert">{aiInsightsError}<button onClick={() => setAiInsightsError("")} aria-label="Dismiss error"><X size={15}/></button></div>}
        {operationsMapError && active === "Operations Map" && <div className="form-error page-error" role="alert">{operationsMapError}<button onClick={() => setOperationsMapError("")} aria-label="Dismiss error"><X size={15}/></button></div>}
        {syncError && active === "Synchronization" && <div className="form-error page-error" role="alert">{syncError}<button onClick={() => setSyncError("")} aria-label="Dismiss error"><X size={15}/></button></div>}
        {!organizationId && active !== "Settings" && <Empty title="No organization access" text="Your account has no active organization assignment. Ask an administrator to grant access."/>}
        {organizationId && !activeSectionAvailable && <Empty title={`${active} is not connected yet`} text="This section will become available when its backend API is ready. Sign-in, users, assets, service requests, incidents, maintenance work orders, coordination, reports, AI insights, and organization site and department lookup are currently connected."/>}
        {organizationId && active === "Dashboard" && <Dashboard assetPage={assetPage} requestPage={requestPage} counts={counts} loading={loading} onOpen={setActive}/>}
        {organizationId && active === "Assets & Equipment" && <AssetsView assets={assets} total={assetPage?.total || 0} loading={loading}/>}
        {organizationId && active === "Asset Categories" && <CategoriesView categories={categoryPage?.items || []} loading={loading}/>}
        {organizationId && active === "Service Requests" && <RequestsView requests={requests} total={requestPage?.total || 0} loading={loading} onAction={(request, action) => { setActionRequest(request); setActionKind(action); setActionValue(""); setActionUser(""); }}/>}
        {organizationId && active === "Incidents" && <IncidentsView
          page={incidentPage}
          sites={sites}
          loading={incidentLoading}
          status={incidentStatusFilter}
          severity={incidentSeverityFilter}
          onStatusChange={value => { setIncidentStatusFilter(value); setIncidentOffset(0); }}
          onSeverityChange={value => { setIncidentSeverityFilter(value); setIncidentOffset(0); }}
          onPageChange={setIncidentOffset}
          onOpen={incident => { setError(""); setSelectedIncident(incident); }}
        />}
        {organizationId && active === "Maintenance" && <MaintenanceView
          page={workOrderPage}
          assets={[...assetOptions, ...(assetPage?.items || [])]}
          loading={workOrderLoading}
          status={workOrderStatusFilter}
          workOrderType={workOrderTypeFilter}
          onStatusChange={value => { setWorkOrderStatusFilter(value); setWorkOrderOffset(0); }}
          onTypeChange={value => { setWorkOrderTypeFilter(value); setWorkOrderOffset(0); }}
          onPageChange={setWorkOrderOffset}
          onOpen={workOrder => { setError(""); setWorkOrderStatus(workOrder.status); setSelectedWorkOrder(workOrder); }}
        />}
        {organizationId && active === "Coordination" && <CoordinationView
          page={coordinationPage}
          loading={coordinationLoading}
          status={coordinationStatusFilter}
          onStatusChange={value => { setCoordinationStatusFilter(value); setCoordinationOffset(0); }}
          onPageChange={setCoordinationOffset}
          onOpen={item => { setCoordinationModalError(""); setSelectedCoordinationOrder(item); }}
        />}
        {organizationId && active === "Reports & Analytics" && <>
          <form className="panel report-controls" onSubmit={applyReportFilters}>
            <label>From<input type="date" required value={reportFilters.start_date} onChange={event => setReportFilters(filters => ({ ...filters, start_date: event.target.value }))}/></label>
            <label>To<input type="date" required value={reportFilters.end_date} onChange={event => setReportFilters(filters => ({ ...filters, end_date: event.target.value }))}/></label>
            <label>Site<select value={reportFilters.site_id} onChange={event => setReportFilters(filters => ({ ...filters, site_id: event.target.value }))}><option value="">All accessible sites</option>{sites.map(site => <option key={site.id} value={site.id}>{site.name}</option>)}</select></label>
            <button type="submit" className="primary-button" disabled={reportsLoading}><BarChart3 size={15}/>{reportsLoading ? "Generating..." : "Generate report"}</button>
            <button type="button" className="secondary-button report-export" disabled={!reportsSnapshot || reportsLoading} onClick={downloadReportsCsv}>Export CSV</button>
          </form>
          <ReportsView snapshot={reportsSnapshot} loading={reportsLoading}/>
        </>}
        {organizationId && active === "AI Insights" && <AIInsightsView
          filters={aiFilters}
          sites={sites}
          consent={aiExternalConsent}
          result={aiInsights}
          loading={aiInsightsLoading}
          onFiltersChange={filters => { setAiFilters(filters); setAiInsights(null); setAiInsightsError(""); }}
          onConsentChange={setAiExternalConsent}
          onSubmit={generateAiInsights}
        />}
        {organizationId && active === "Operations Map" && <OperationsMapView snapshot={operationsMapOrganizationId === organizationId ? operationsMap : null} loading={operationsMapLoading}/>}
        {organizationId && active === "Synchronization" && <SynchronizationView
          operations={syncOperations}
          online={isOnline}
          loading={syncLoading}
          lastSyncAt={lastSyncAt}
          onSync={synchronizeNow}
          onRetry={retrySynchronizationOperation}
          onDiscard={discardSynchronizationOperation}
        />}
        {active === "Settings" && <SettingsView
          key={`${organizationId}:${user.display_name}:${org?.name || ""}:${org?.code || ""}`}
          user={user}
          organization={org}
          dark={dark}
          online={isOnline}
          profileSaving={profileSaving}
          organizationSaving={organizationSaving}
          error={settingsError}
          notice={settingsNotice}
          onProfileSave={saveProfile}
          onOrganizationSave={saveOrganization}
          onThemeChange={setDark}
        />}
      </main>
    </div>

    {modal && <Modal title={modal === "asset" ? "Create asset" : modal === "category" ? "Create asset category" : modal === "request" ? "Submit service request" : modal === "incident" ? "Report incident" : modal === "workOrder" ? "Schedule maintenance work" : "Register maintenance technician"} onClose={() => setModal("")}><form className="data-form" onSubmit={submitForm}>
      {modal === "asset" && <><label>Asset tag<input name="asset_tag" required maxLength={100}/></label><label>Name<input name="name" required maxLength={200}/></label><label>Category<select name="category_id" required defaultValue=""><option value="" disabled>Select category</option>{(categoryPage?.items || []).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Site<select name="site_id" required defaultValue=""><option value="" disabled>Select accessible site</option>{sites.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Department<select name="department_id" defaultValue=""><option value="">No department</option>{departments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Status<select name="status"><option value="in_service">In service</option><option value="under_maintenance">Under maintenance</option><option value="out_of_service">Out of service</option><option value="retired">Retired</option></select></label><label>Criticality<select name="criticality"><option>low</option><option selected>medium</option><option>high</option><option>critical</option></select></label></>}
      {modal === "category" && <><label>Name<input name="name" required maxLength={150}/></label><label>Code<input name="code" required maxLength={80}/></label><label>Description<textarea name="description"/></label></>}
      {modal === "request" && <><label>Title<input name="title" required minLength={3} maxLength={200}/></label><label>Description<textarea name="description" required minLength={5} maxLength={10000}/></label><label>Site<select name="site_id" required defaultValue=""><option value="" disabled>Select accessible site</option>{sites.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Department<select name="department_id" defaultValue=""><option value="">No department</option>{departments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Related asset<select name="asset_id" defaultValue=""><option value="">No asset</option>{(assetPage?.items || []).map(item => <option key={item.id} value={item.id}>{item.asset_tag} · {item.name}</option>)}</select></label><label>Category<input name="category" required minLength={2} maxLength={50} defaultValue="general"/></label><label>Priority<select name="priority"><option>low</option><option>normal</option><option>high</option><option>urgent</option></select></label><label className="checkbox-label"><input name="safety_critical" type="checkbox"/>Safety critical</label></>}
      {modal === "incident" && <><label>Title<input name="title" required minLength={3} maxLength={200}/></label><label>Category<select name="category" defaultValue="other"><option value="safety">Safety</option><option value="near_miss">Near miss</option><option value="equipment_damage">Equipment damage</option><option value="environmental">Environmental</option><option value="security">Security</option><option value="other">Other</option></select></label><label>Severity<select name="severity" defaultValue="medium"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label><label>Site<select name="site_id" required defaultValue=""><option value="" disabled>Select accessible site</option>{sites.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Department<select name="department_id" defaultValue=""><option value="">No department</option>{departments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Related asset<select name="asset_id" defaultValue=""><option value="">No asset</option>{assetOptions.map(item => <option key={item.id} value={item.id}>{item.asset_tag} · {item.name}</option>)}</select></label><label>Date and time<input name="occurred_at" type="datetime-local" required/></label><label>Description<textarea name="description" required minLength={5} maxLength={10000}/></label></>}
      {modal === "incident" && error && <div className="form-error" role="alert">{error}</div>}
      {modal === "workOrder" && <><label>Work order title<input name="title" required minLength={3} maxLength={200}/></label><label>Maintenance type<select name="work_order_type" defaultValue="preventive"><option value="preventive">Preventive</option><option value="corrective">Corrective</option></select></label><label>Asset<select name="asset_id" required defaultValue="" disabled={assetOptionsLoading || !assetOptions.length}><option value="" disabled>{assetOptionsLoading ? "Loading accessible assets..." : "Select an accessible asset"}</option>{assetOptions.map(item => <option key={item.id} value={item.id}>{item.asset_tag} · {item.name}</option>)}</select></label><label>Priority<select name="priority" defaultValue="normal"><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label><label>Scheduled date and time<input name="scheduled_at" type="datetime-local" required/></label><label>Task description<textarea name="description" required minLength={5} maxLength={10000}/></label></>}
      {modal === "workOrder" && assetOptionsError && <div className="form-error" role="alert">{assetOptionsError}</div>}
      {modal === "workOrder" && error && <div className="form-error" role="alert">{error}</div>}
      {modal === "user" && <><label>Full name<input name="display_name" required maxLength={150}/></label><label>Email<input name="email" type="email" required maxLength={320}/></label><label>Initial password<input name="initial_password" type="password" required minLength={12} maxLength={128} autoComplete="new-password"/><small>The technician can use this password to sign in.</small></label><fieldset className="location-checks"><legend>Sites <span>Choose at least one</span></legend>{sites.map(site => <label key={site.id}><input type="checkbox" name="site_ids" value={site.id}/>{site.name}</label>)}</fieldset>{departments.length > 0 && <fieldset className="location-checks"><legend>Departments <span>Optional</span></legend>{departments.map(department => <label key={department.id}><input type="checkbox" name="department_ids" value={department.id}/>{department.name}</label>)}</fieldset>}<p className="modal-description">Role: Maintenance Technician</p></>}
      <div className="form-actions"><button type="button" className="secondary-button" onClick={() => setModal("")}>Cancel</button><button className="primary-button" disabled={submitting}>{submitting ? "Saving" : "Submit"}</button></div>
    </form></Modal>}

    {selectedIncident && <Modal title={`${selectedIncident.incident_number} · Incident details`} onClose={() => setSelectedIncident(null)}><form className="data-form" onSubmit={submitIncidentUpdate}>
      <p className="modal-description">{selectedIncident.title} · {new Date(selectedIncident.occurred_at).toLocaleString()}</p>
      <p className="incident-description">{selectedIncident.description}</p>
      <label>Status<select name="status" defaultValue={selectedIncident.status} disabled={selectedIncident.status === "closed"}>{[selectedIncident.status, ...incidentTransitions[selectedIncident.status]].map(value => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label>
      <label>Resolution<textarea name="resolution" defaultValue={selectedIncident.resolution || ""} maxLength={10000}/></label>
      {error && <div className="form-error" role="alert">{error}</div>}
      <div className="form-actions"><button type="button" className="secondary-button" onClick={() => setSelectedIncident(null)}>Close</button>{selectedIncident.status !== "closed" && <button className="primary-button" disabled={submitting}>{submitting ? "Saving" : "Save update"}</button>}</div>
    </form></Modal>}

    {selectedWorkOrder && <Modal title={`${selectedWorkOrder.work_order_number} · Work order`} onClose={() => setSelectedWorkOrder(null)}><form className="data-form" onSubmit={submitWorkOrderTransition}>
      <p className="modal-description">{selectedWorkOrder.title} · {new Date(selectedWorkOrder.scheduled_at).toLocaleString()}</p>
      <p className="incident-description">{selectedWorkOrder.description}</p>
      <div className="work-order-meta"><span>{selectedWorkOrder.work_order_type}</span><span>{selectedWorkOrder.priority} priority</span><span>{selectedWorkOrder.status.replaceAll("_", " ")}</span></div>
      {selectedWorkOrder.status !== "completed" && selectedWorkOrder.status !== "cancelled" && <><label>Status<select name="status" value={workOrderStatus} onChange={event => setWorkOrderStatus(event.target.value as MaintenanceWorkOrderStatus)}>{[selectedWorkOrder.status, ...workOrderTransitions[selectedWorkOrder.status]].map(value => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label><label>Completion note<textarea name="completion_note" defaultValue={selectedWorkOrder.completion_note || ""} required={workOrderStatus === "completed"} maxLength={10000}/></label></>}
      {selectedWorkOrder.completion_note && <p className="incident-description">{selectedWorkOrder.completion_note}</p>}
      {error && <div className="form-error" role="alert">{error}</div>}
      <div className="form-actions"><button type="button" className="secondary-button" onClick={() => setSelectedWorkOrder(null)}>Close</button>{selectedWorkOrder.status !== "completed" && selectedWorkOrder.status !== "cancelled" && <button className="primary-button" disabled={submitting || workOrderStatus === selectedWorkOrder.status}>{submitting ? "Saving" : "Save status"}</button>}</div>
    </form></Modal>}

    {selectedCoordinationOrder && <Modal title={`${selectedCoordinationOrder.work_order.work_order_number} · Assign and hand off`} onClose={() => setSelectedCoordinationOrder(null)}><form className="data-form" onSubmit={submitCoordinationAssignment}>
      <p className="modal-description">{selectedCoordinationOrder.work_order.title} · {new Date(selectedCoordinationOrder.work_order.scheduled_at).toLocaleString()}</p>
      {selectedCoordinationOrder.current_assignment && <p className="coordination-current">Currently assigned to <strong>{selectedCoordinationOrder.current_assignment.assignee_name}</strong></p>}
      {coordinationModalLoading ? <div className="table-state"><LoaderCircle className="spin" size={19}/>Loading eligible technicians...</div> : <label>Assign to<select name="assigned_to" required defaultValue=""><option value="" disabled>Select an eligible technician</option>{coordinationTechnicians.map(technician => <option key={technician.id} value={technician.id}>{technician.display_name} · {technician.email}</option>)}</select></label>}
      <label>Handoff note<textarea name="handoff_note" maxLength={5000} placeholder="Context, next steps, or safety notes for the technician"/></label>
      {coordinationHistory.length > 0 && <section className="handoff-history"><h3>Assignment history</h3>{coordinationHistory.map(item => <article key={item.id}><strong>{item.assignee_name}</strong><span>Assigned by {item.assigner_name} · {new Date(item.assigned_at).toLocaleString()}</span>{item.handoff_note && <p>{item.handoff_note}</p>}</article>)}</section>}
      {coordinationModalError && <div className="form-error" role="alert">{coordinationModalError}</div>}
      {!coordinationModalLoading && coordinationTechnicians.length === 0 && !coordinationModalError && <p className="modal-description">No active maintenance technicians currently have access to this work order's site and department.</p>}
      <div className="form-actions"><button type="button" className="secondary-button" onClick={() => setSelectedCoordinationOrder(null)}>Cancel</button><button className="primary-button" disabled={submitting || coordinationModalLoading || !coordinationTechnicians.length}>{submitting ? "Saving" : "Save assignment"}</button></div>
    </form></Modal>}

    {actionRequest && <Modal title={`${actionKind} service request`} onClose={() => setActionRequest(null)}><form className="data-form" onSubmit={submitAction}><p className="modal-description">{actionRequest.request_number} · {actionRequest.title}</p>{actionKind === "transition" ? <label>New status<select required value={actionValue} onChange={event => setActionValue(event.target.value)}><option value="">Select status</option>{(transitions[actionRequest.status] || []).map(value => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label> : actionKind === "assign" ? <label>Assignee user ID<input required value={actionUser} onChange={event => setActionUser(event.target.value)} placeholder="User UUID"/></label> : actionKind !== "approve" && <label>{actionKind === "reject" ? "Reason" : "Note"}<textarea required={actionKind === "reject"} minLength={actionKind === "reject" ? 3 : undefined} value={actionValue} onChange={event => setActionValue(event.target.value)}/></label>}{actionKind === "assign" && <label>Assignment note<textarea value={actionValue} onChange={event => setActionValue(event.target.value)}/></label>}<div className="form-actions"><button type="button" className="secondary-button" onClick={() => setActionRequest(null)}>Cancel</button><button className="primary-button" disabled={submitting}>{submitting ? "Saving" : `Confirm ${actionKind}`}</button></div></form></Modal>}
  </div>;
}

function Login({ onSubmit, busy, error }: { onSubmit: (email: string, password: string) => void; busy: boolean; error: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  return <main className="login-screen"><div className="login-brand"><span><Shield size={28}/></span><div><strong>OxMaint</strong><small>Operations · Support · Resilience</small></div></div><form className="login-panel" onSubmit={event => { event.preventDefault(); onSubmit(email, password); }}><p className="eyebrow">WORKSPACE ACCESS</p><h1>Sign in</h1><p className="login-description">Use your OxMaint account to access your organization workspace.</p>{error && <div className="form-error" role="alert">{error}</div>}<label>Email address<input type="email" autoComplete="username" required value={email} onChange={event => setEmail(event.target.value)}/></label><label>Password<input type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)}/></label><button className="primary-button login-submit" disabled={busy}>{busy ? "Signing in..." : "Sign in"}</button></form><p className="login-foot">Secure access · OxMaint</p></main>;
}

function Dashboard({ assetPage, requestPage, counts, loading, onOpen }: { assetPage: Page<Asset> | null; requestPage: Page<ServiceRequest> | null; counts: { inService: number; maintenance: number; outOfService: number; retired: number; submitted: number; underReview: number }; loading: boolean; onOpen: (section: string) => void }) {
  const assetItems = assetPage?.items || [];
  const requestItems = requestPage?.items || [];
  const statusItems = [
    ["In service", counts.inService],
    ["Under maintenance", counts.maintenance],
    ["Out of service", counts.outOfService],
    ["Retired", counts.retired]
  ] as const;
  return <>
    <div className="stats-grid data-stats"><Stat label="Active assets" value={assetPage?.total ?? "-"} icon={Package} tone="blue"/><Stat label="Under maintenance" value={counts.maintenance} icon={Wrench} tone="orange"/><Stat label="Out of service" value={counts.outOfService} icon={AlertTriangle} tone="red"/><Stat label="Open requests" value={counts.submitted + counts.underReview} icon={ClipboardList} tone="green"/></div>
    <div className="data-dashboard-grid"><section className="panel data-panel"><div className="panel-heading"><div className="panel-title"><h2>Recent service requests</h2></div><button className="text-action" onClick={() => onOpen("Service Requests")}>All requests <ArrowUpRight size={14}/></button></div><DataTable loading={loading} empty={!requestItems.length}><table><thead><tr><th>Request</th><th>Title</th><th>Priority</th><th>Status</th></tr></thead><tbody>{requestItems.slice(0, 6).map(item => <tr key={item.id}><td><strong>{item.request_number}</strong></td><td>{item.title}</td><td><Badge value={item.priority}/></td><td><Badge value={item.status}/></td></tr>)}</tbody></table></DataTable></section>
      <section className="panel data-panel"><div className="panel-heading"><div className="panel-title"><h2>Asset status</h2></div><button className="text-action" onClick={() => onOpen("Assets & Equipment")}>All assets <ArrowUpRight size={14}/></button></div><div className="status-breakdown">{statusItems.map(([label, count]) => <div key={label}><span className={`status-mark ${label.toLowerCase().replaceAll(" ", "-")}`}/><span>{label}</span><strong>{count}</strong></div>)}</div><div className="dashboard-total"><span>Active assets in organization</span><strong>{assetPage?.total ?? 0}</strong></div></section>
      <section className="panel data-panel"><div className="panel-heading"><div className="panel-title"><h2>Recently added assets</h2></div><button className="text-action" onClick={() => onOpen("Assets & Equipment")}>Manage assets <ArrowUpRight size={14}/></button></div><DataTable loading={loading} empty={!assetItems.length}><table><thead><tr><th>Tag</th><th>Asset</th><th>Status</th></tr></thead><tbody>{assetItems.slice(0, 6).map(item => <tr key={item.id}><td><strong>{item.asset_tag}</strong></td><td>{item.name}</td><td><Badge value={item.status}/></td></tr>)}</tbody></table></DataTable></section></div>
  </>;
}

function AssetsView({ assets, total, loading }: { assets: Asset[]; total: number; loading: boolean }) {
  return <section className="panel data-panel"><div className="panel-heading"><div className="panel-title"><h2>{total} accessible assets</h2></div></div><DataTable loading={loading} empty={!assets.length}><div className="table-scroll"><table><thead><tr><th>Tag</th><th>Name</th><th>Status</th><th>Criticality</th><th>Manufacturer</th><th>Serial</th></tr></thead><tbody>{assets.map(item => <tr key={item.id}><td><strong>{item.asset_tag}</strong></td><td>{item.name}</td><td><Badge value={item.status}/></td><td><Badge value={item.criticality}/></td><td>{item.manufacturer || "-"}</td><td>{item.serial_number || "-"}</td></tr>)}</tbody></table></div></DataTable></section>;
}

function CategoriesView({ categories, loading }: { categories: AssetCategory[]; loading: boolean }) {
  return <section className="panel data-panel"><div className="panel-heading"><div className="panel-title"><h2>{categories.length} asset categories</h2></div></div><DataTable loading={loading} empty={!categories.length}><div className="table-scroll"><table><thead><tr><th>Code</th><th>Name</th><th>Description</th><th>Status</th></tr></thead><tbody>{categories.map(item => <tr key={item.id}><td><strong>{item.code}</strong></td><td>{item.name}</td><td>{item.description || "-"}</td><td><Badge value="active"/></td></tr>)}</tbody></table></div></DataTable></section>;
}

function RequestsView({ requests, total, loading, onAction }: { requests: ServiceRequest[]; total: number; loading: boolean; onAction: (request: ServiceRequest, action: string) => void }) {
  return <section className="panel data-panel"><div className="panel-heading"><div className="panel-title"><h2>{total} service requests</h2></div></div><DataTable loading={loading} empty={!requests.length}><div className="table-scroll"><table><thead><tr><th>Request</th><th>Title</th><th>Priority</th><th>Status</th><th>Submitted</th><th>Actions</th></tr></thead><tbody>{requests.map(item => <tr key={item.id}><td><strong>{item.request_number}</strong></td><td>{item.title}</td><td><Badge value={item.priority}/></td><td><Badge value={item.status}/></td><td>{new Date(item.submitted_at).toLocaleDateString()}</td><td><div className="action-buttons">{item.status === "submitted" && <button onClick={() => onAction(item, "review")}>Review</button>}{item.status === "under_review" && <><button onClick={() => onAction(item, "approve")}>Approve</button><button onClick={() => onAction(item, "reject")}>Reject</button></>}{["under_review", "approved", "assigned"].includes(item.status) && <button onClick={() => onAction(item, "assign")}>Assign</button>}{transitions[item.status] && <button onClick={() => onAction(item, "transition")}>Change status</button>}</div></td></tr>)}</tbody></table></div></DataTable></section>;
}

function IncidentsView({ page, sites, loading, status, severity, onStatusChange, onSeverityChange, onPageChange, onOpen }: {
  page: Page<Incident> | null;
  sites: LocationOption[];
  loading: boolean;
  status: IncidentStatus | "";
  severity: IncidentSeverity | "";
  onStatusChange: (value: IncidentStatus | "") => void;
  onSeverityChange: (value: IncidentSeverity | "") => void;
  onPageChange: (offset: number) => void;
  onOpen: (incident: Incident) => void;
}) {
  const incidents = page?.items || [];
  const total = page?.total || 0;
  const firstItem = total ? (page?.offset || 0) + 1 : 0;
  const lastItem = Math.min((page?.offset || 0) + incidents.length, total);

  return <section className="panel data-panel">
    <div className="panel-heading incident-heading">
      <div className="panel-title"><h2>{total} incidents</h2></div>
      <div className="incident-filters">
        <select aria-label="Filter incidents by status" value={status} onChange={event => onStatusChange(event.target.value as IncidentStatus | "")}>
          <option value="">All statuses</option>
          <option value="reported">Reported</option>
          <option value="investigating">Investigating</option>
          <option value="resolved">Resolved</option>
          <option value="closed">Closed</option>
        </select>
        <select aria-label="Filter incidents by severity" value={severity} onChange={event => onSeverityChange(event.target.value as IncidentSeverity | "")}>
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>
    </div>
    <DataTable loading={loading} empty={!incidents.length}>
      <div className="table-scroll"><table className="incident-table">
        <thead><tr><th>Incident</th><th>Title</th><th>Site</th><th>Category</th><th>Severity</th><th>Status</th><th>Occurred</th><th></th></tr></thead>
        <tbody>{incidents.map(item => <tr key={item.id}>
          <td><strong>{item.incident_number}</strong></td>
          <td>{item.title}</td>
          <td>{sites.find(site => site.id === item.site_id)?.name || "—"}</td>
          <td>{item.category.replaceAll("_", " ")}</td>
          <td><span className={`priority priority-${item.severity}`}>{item.severity}</span></td>
          <td><Badge value={item.status}/></td>
          <td>{new Date(item.occurred_at).toLocaleString()}</td>
          <td><button className="text-action" onClick={() => onOpen(item)}>Details</button></td>
        </tr>)}</tbody>
      </table></div>
    </DataTable>
    <div className="incident-pagination">
      <span>Showing {firstItem}–{lastItem} of {total}</span>
      <div><button className="secondary-button" disabled={loading || !page || page.offset === 0} onClick={() => onPageChange(Math.max(0, (page?.offset || 0) - (page?.limit || 25)))}>Previous</button><button className="secondary-button" disabled={loading || !page?.has_more} onClick={() => onPageChange((page?.offset || 0) + (page?.limit || 25))}>Next</button></div>
    </div>
  </section>;
}

function MaintenanceView({ page, assets, loading, status, workOrderType, onStatusChange, onTypeChange, onPageChange, onOpen }: {
  page: Page<MaintenanceWorkOrder> | null;
  assets: Asset[];
  loading: boolean;
  status: MaintenanceWorkOrderStatus | "";
  workOrderType: MaintenanceWorkOrderType | "";
  onStatusChange: (value: MaintenanceWorkOrderStatus | "") => void;
  onTypeChange: (value: MaintenanceWorkOrderType | "") => void;
  onPageChange: (offset: number) => void;
  onOpen: (workOrder: MaintenanceWorkOrder) => void;
}) {
  const workOrders = page?.items || [];
  const total = page?.total || 0;
  const firstItem = total ? (page?.offset || 0) + 1 : 0;
  const lastItem = Math.min((page?.offset || 0) + workOrders.length, total);

  return <section className="panel data-panel">
    <div className="panel-heading maintenance-heading">
      <div className="panel-title"><h2>{total} maintenance work orders</h2></div>
      <div className="incident-filters">
        <select aria-label="Filter work orders by status" value={status} onChange={event => onStatusChange(event.target.value as MaintenanceWorkOrderStatus | "")}>
          <option value="">All statuses</option>
          <option value="scheduled">Scheduled</option>
          <option value="in_progress">In progress</option>
          <option value="waiting">Waiting</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <select aria-label="Filter work orders by type" value={workOrderType} onChange={event => onTypeChange(event.target.value as MaintenanceWorkOrderType | "")}>
          <option value="">All types</option>
          <option value="preventive">Preventive</option>
          <option value="corrective">Corrective</option>
        </select>
      </div>
    </div>
    <DataTable loading={loading} empty={!workOrders.length}>
      <div className="table-scroll"><table className="maintenance-table">
        <thead><tr><th>Work order</th><th>Task</th><th>Asset</th><th>Type</th><th>Priority</th><th>Status</th><th>Scheduled</th><th></th></tr></thead>
        <tbody>{workOrders.map(item => {
          const asset = assets.find(candidate => candidate.id === item.asset_id);
          return <tr key={item.id}>
            <td><strong>{item.work_order_number}</strong></td>
            <td>{item.title}</td>
            <td>{asset ? `${asset.asset_tag} · ${asset.name}` : "Asset details unavailable"}</td>
            <td><span className={`work-order-type ${item.work_order_type}`}>{item.work_order_type}</span></td>
            <td><span className={`priority priority-${item.priority}`}>{item.priority}</span></td>
            <td><Badge value={item.status}/></td>
            <td>{new Date(item.scheduled_at).toLocaleString()}</td>
            <td><button className="text-action" onClick={() => onOpen(item)}>Details</button></td>
          </tr>;
        })}</tbody>
      </table></div>
    </DataTable>
    <div className="incident-pagination">
      <span>Showing {firstItem}–{lastItem} of {total}</span>
      <div><button className="secondary-button" disabled={loading || !page || page.offset === 0} onClick={() => onPageChange(Math.max(0, (page?.offset || 0) - (page?.limit || 25)))}>Previous</button><button className="secondary-button" disabled={loading || !page?.has_more} onClick={() => onPageChange((page?.offset || 0) + (page?.limit || 25))}>Next</button></div>
    </div>
  </section>;
}

function CoordinationView({ page, loading, status, onStatusChange, onPageChange, onOpen }: {
  page: Page<CoordinationWorkOrder> | null;
  loading: boolean;
  status: MaintenanceWorkOrderStatus | "";
  onStatusChange: (value: MaintenanceWorkOrderStatus | "") => void;
  onPageChange: (offset: number) => void;
  onOpen: (item: CoordinationWorkOrder) => void;
}) {
  const items = page?.items || [];
  const total = page?.total || 0;
  const firstItem = total ? (page?.offset || 0) + 1 : 0;
  const lastItem = Math.min((page?.offset || 0) + items.length, total);

  return <section className="panel data-panel">
    <div className="panel-heading maintenance-heading">
      <div className="panel-title"><h2>{total} work orders to coordinate</h2></div>
      <div className="incident-filters">
        <select aria-label="Filter coordinated work by status" value={status} onChange={event => onStatusChange(event.target.value as MaintenanceWorkOrderStatus | "")}>
          <option value="">All statuses</option>
          <option value="scheduled">Scheduled</option>
          <option value="in_progress">In progress</option>
          <option value="waiting">Waiting</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>
    </div>
    <DataTable loading={loading} empty={!items.length}>
      <div className="table-scroll"><table className="coordination-table">
        <thead><tr><th>Work order</th><th>Task</th><th>Priority</th><th>Status</th><th>Scheduled</th><th>Assigned technician</th><th></th></tr></thead>
        <tbody>{items.map(item => <tr key={item.work_order.id}>
          <td><strong>{item.work_order.work_order_number}</strong></td>
          <td>{item.work_order.title}</td>
          <td><span className={`priority priority-${item.work_order.priority}`}>{item.work_order.priority}</span></td>
          <td><Badge value={item.work_order.status}/></td>
          <td>{new Date(item.work_order.scheduled_at).toLocaleString()}</td>
          <td>{item.current_assignment?.assignee_name || <span className="coordination-unassigned">Unassigned</span>}</td>
          <td><button className="text-action" onClick={() => onOpen(item)}>{item.current_assignment ? "Handoff" : "Assign"}</button></td>
        </tr>)}</tbody>
      </table></div>
    </DataTable>
    <div className="incident-pagination">
      <span>Showing {firstItem}–{lastItem} of {total}</span>
      <div><button className="secondary-button" disabled={loading || !page || page.offset === 0} onClick={() => onPageChange(Math.max(0, (page?.offset || 0) - (page?.limit || 25)))}>Previous</button><button className="secondary-button" disabled={loading || !page?.has_more} onClick={() => onPageChange((page?.offset || 0) + (page?.limit || 25))}>Next</button></div>
    </div>
  </section>;
}

function SettingsView({
  user,
  organization,
  dark,
  online,
  profileSaving,
  organizationSaving,
  error,
  notice,
  onProfileSave,
  onOrganizationSave,
  onThemeChange,
}: {
  user: User;
  organization?: Organization;
  dark: boolean;
  online: boolean;
  profileSaving: boolean;
  organizationSaving: boolean;
  error: string;
  notice: string;
  onProfileSave: (event: FormEvent<HTMLFormElement>) => void;
  onOrganizationSave: (event: FormEvent<HTMLFormElement>) => void;
  onThemeChange: (dark: boolean) => void;
}) {
  const canUpdateOrganization = Boolean(organization?.can_update);
  return <div className="settings-grid">
    {error && <div className="form-error settings-message" role="alert">{error}</div>}
    {notice && <div className="notice settings-message" role="status"><CheckCircle2 size={16}/>{notice}</div>}
    <section className="panel settings-card">
      <div className="panel-heading">
        <div className="panel-title"><Users size={16}/><h2>Personal account</h2></div>
        <span className="settings-caption">Your workspace identity</span>
      </div>
      <div className="settings-card-body">
        <form className="settings-form" onSubmit={onProfileSave}>
          <label>Display name<input name="display_name" required minLength={1} maxLength={150} defaultValue={user.display_name} readOnly={!online}/></label>
          <label>Email address<input value={user.email} readOnly/></label>
          <div className="settings-form-footer">
            <span>Changes update your account profile.</span>
            <button type="submit" className="primary-button" disabled={!online || profileSaving}>
              {profileSaving ? "Saving..." : "Save profile"}
            </button>
          </div>
          {!online && <small className="settings-hint">Connect to the server to update your profile.</small>}
        </form>
        <div className="settings-theme">
          <div><strong>Appearance</strong><span>Choose the dashboard theme for this browser.</span></div>
          <div className="settings-theme-toggle">
            <Moon size={16}/>
            <button type="button" aria-label="Toggle dark theme" aria-pressed={dark} onClick={() => onThemeChange(!dark)} className={`switch ${dark ? "on" : ""}`}><span/></button>
            <Sun size={16}/>
            <b>{dark ? "Dark" : "Light"}</b>
          </div>
        </div>
      </div>
    </section>
    <section className="panel settings-card">
      <div className="panel-heading">
        <div className="panel-title"><Building2 size={16}/><h2>Organization profile</h2></div>
        {organization && <span className="settings-caption">{canUpdateOrganization ? "Manager access" : "Read only"}</span>}
      </div>
      {!organization ? <div className="settings-card-body"><Empty title="Select an organization" text="Choose an organization from the top bar to view its profile."/></div> :
        <div className="settings-card-body">
          <form className="settings-form" onSubmit={onOrganizationSave}>
            <label>Organization name<input name="name" required minLength={1} maxLength={150} defaultValue={organization.name} readOnly={!canUpdateOrganization || !online}/></label>
            <label>Organization code<input name="code" required minLength={1} maxLength={50} defaultValue={organization.code} readOnly={!canUpdateOrganization || !online}/></label>
            <label>Description<textarea name="description" maxLength={5000} defaultValue={organization.description || ""} readOnly={!canUpdateOrganization || !online}/></label>
            {canUpdateOrganization ?
              <div className="settings-form-footer">
                <span>Only organization managers can change these details.</span>
                <button type="submit" className="primary-button" disabled={!online || organizationSaving}>
                  {organizationSaving ? "Saving..." : "Save organization"}
                </button>
              </div> :
              <small className="settings-hint">Contact an organization manager to change these details.</small>}
            {!online && canUpdateOrganization && <small className="settings-hint">Connect to the server to edit organization settings.</small>}
          </form>
        </div>}
    </section>
  </div>;
}

function SynchronizationView({ operations, online, loading, lastSyncAt, onSync, onRetry, onDiscard }: {
  operations: LocalSyncOperation[];
  online: boolean;
  loading: boolean;
  lastSyncAt?: string;
  onSync: () => void;
  onRetry: (operationId: string) => void;
  onDiscard: (operationId: string) => void;
}) {
  const pending = operations.filter(operation => operation.state === "pending");
  const conflicts = operations.filter(operation => operation.state === "conflict");
  const labels: Record<LocalSyncOperation["operation_type"], string> = {
    "service_request.create": "New service request",
    "service_request.transition": "Service request status change",
    "incident.create": "New incident report",
    "incident.update": "Incident update",
    "maintenance_work_order.create": "New work order",
    "maintenance_work_order.transition": "Work order status change",
  };
  return <>
    <div className="stats-grid data-stats sync-stats">
      <Stat label="Connection" value={online ? "Online" : "Offline"} icon={RefreshCw} tone={online ? "green" : "orange"}/>
      <Stat label="Waiting to sync" value={pending.length} icon={ClipboardList} tone="blue"/>
      <Stat label="Needs review" value={conflicts.length} icon={AlertTriangle} tone="red"/>
      <Stat label="Last successful sync" value={lastSyncAt ? new Date(lastSyncAt).toLocaleTimeString() : "—"} icon={CheckCircle2} tone="green"/>
    </div>
    <section className="panel data-panel sync-workspace">
      <div className="panel-heading sync-heading">
        <div className="panel-title"><h2>Offline synchronization</h2><span>Changes are sent securely when this device reconnects.</span></div>
        <button className="primary-button" disabled={!online || loading || pending.length === 0} onClick={onSync}>
          <RefreshCw size={14} className={loading ? "spin" : ""}/>{loading ? "Syncing..." : "Sync now"}
        </button>
      </div>
      {!operations.length ? <Empty title={online ? "Everything is synchronized" : "Ready for offline work"} text={online ? "No queued changes need to be sent." : "Previously loaded sites, assets, requests, incidents, and work orders are available from this device for up to 24 hours."}/> :
        <div className="sync-operation-list">{operations.map(operation => {
          const title = typeof operation.payload.title === "string"
            ? operation.payload.title
            : typeof operation.payload.new_status === "string"
              ? `Status → ${operation.payload.new_status.replaceAll("_", " ")}`
              : "Queued change";
          return <article className={`sync-operation ${operation.state}`} key={operation.operation_id}>
            <div className="sync-operation-icon">{operation.state === "conflict" ? <AlertTriangle size={16}/> : <RefreshCw size={16}/>}</div>
            <div className="sync-operation-copy">
              <strong>{labels[operation.operation_type]}</strong>
              <span>{title} · {new Date(operation.created_at).toLocaleString()}</span>
              {operation.last_error && <p role="alert">{operation.last_error}</p>}
            </div>
            {operation.state === "conflict" && <div className="sync-operation-actions">
              <button className="secondary-button" disabled={!online || loading} onClick={() => onRetry(operation.operation_id)}>Retry</button>
              <button className="text-action" onClick={() => onDiscard(operation.operation_id)}>Discard</button>
            </div>}
            {operation.state === "pending" && <span className="sync-operation-state">Waiting to sync</span>}
          </article>;
        })}</div>}
      <div className="sync-privacy-note">
        Cached records and pending form data are stored in this browser’s IndexedDB on this device. Cached reads expire after 24 hours. The last synchronized ordinary edit wins; state changes still require current server permission and a valid workflow transition. Conflicts can be retried after they are resolved or discarded. Approvals and technician assignments require a connection.
      </div>
    </section>
  </>;
}

function OperationsMapView({ snapshot, loading }: {
  snapshot: OperationsMapSnapshot | null;
  loading: boolean;
}) {
  if (loading && !snapshot) {
    return <div className="panel table-state"><LoaderCircle className="spin" size={19}/>Loading site operations...</div>;
  }
  if (!snapshot) return null;

  return <>
    <div className="stats-grid data-stats operations-map-stats">
      <Stat label="Accessible sites" value={snapshot.summary.sites} icon={Building2} tone="blue"/>
      <Stat label="Active assets" value={snapshot.summary.assets} icon={Package} tone="green"/>
      <Stat label="Open requests" value={snapshot.summary.open_requests} icon={ClipboardList} tone="orange"/>
      <Stat label="Open incidents" value={snapshot.summary.open_incidents} icon={AlertTriangle} tone="red"/>
      <Stat label="Overdue work orders" value={snapshot.summary.overdue_work_orders} icon={Wrench} tone="orange"/>
    </div>
    <section className="panel data-panel operations-map-panel">
      <div className="panel-heading">
        <div className="panel-title"><h2>Site operations board</h2><span>Live status for sites you can access</span></div>
        <span className="report-period">{loading ? "Refreshing..." : `Updated ${new Date(snapshot.generated_at).toLocaleTimeString()}`}</span>
      </div>
      {!snapshot.sites.length ? <Empty title="No accessible sites" text="Active sites will appear here when your account is granted site access."/> :
        <div className="operations-site-grid">{snapshot.sites.map(site => {
          const needsAttention = site.high_severity_incidents > 0 || site.overdue_work_orders > 0;
          const assetTotal = Math.max(1, site.assets);
          return <article className={`operations-site-card ${needsAttention ? "needs-attention" : ""}`} key={site.site_id}>
            <header className="operations-site-heading">
              <div><span className="operations-site-code">{site.code}</span><h3>{site.name}</h3>{site.address && <p>{site.address}</p>}</div>
              <span className={`operations-site-status ${needsAttention ? "attention" : "stable"}`}>{needsAttention ? "Needs attention" : "Operational"}</span>
            </header>
            <div className="operations-site-metrics">
              <div><span>Assets</span><strong>{site.assets}</strong></div>
              <div><span>Requests</span><strong>{site.open_requests}</strong></div>
              <div><span>Incidents</span><strong>{site.open_incidents}</strong></div>
              <div><span>Work orders</span><strong>{site.open_work_orders}</strong></div>
            </div>
            <div className="operations-asset-breakdown">
              {Object.entries({
                in_service: "In service",
                under_maintenance: "In maintenance",
                out_of_service: "Out of service",
                retired: "Retired"
              }).map(([status, label]) => {
                const count = site.asset_status[status] || 0;
                return <div key={status}><span>{label}</span><strong>{count}</strong><i><b className={`asset-status-${status}`} style={{ width: `${count / assetTotal * 100}%` }}/></i></div>;
              })}
            </div>
            {(site.high_severity_incidents > 0 || site.overdue_work_orders > 0) && <div className="operations-site-alerts">
              {site.high_severity_incidents > 0 && <span><AlertTriangle size={13}/>{site.high_severity_incidents} high-severity open incident{site.high_severity_incidents === 1 ? "" : "s"}</span>}
              {site.overdue_work_orders > 0 && <span><Wrench size={13}/>{site.overdue_work_orders} overdue work order{site.overdue_work_orders === 1 ? "" : "s"}</span>}
            </div>}
          </article>;
        })}</div>}
      <p className="report-footnote">High-severity incidents include open high and critical incidents. Overdue work orders are active scheduled, in-progress, or waiting tasks past their scheduled time. Generated {new Date(snapshot.generated_at).toLocaleString()}.</p>
    </section>
  </>;
}

function ReportsView({ snapshot, loading }: {
  snapshot: ReportsSnapshot | null;
  loading: boolean;
}) {
  if (loading && !snapshot) {
    return <div className="panel table-state"><LoaderCircle className="spin" size={19}/>Generating report from live data...</div>;
  }
  if (!snapshot) return null;

  const maxRequests = Math.max(1, ...snapshot.daily_trend.map(item => item.requests));
  const maxIncidents = Math.max(1, ...snapshot.daily_trend.map(item => item.incidents));
  const maxWorkOrders = Math.max(1, ...snapshot.daily_trend.map(item => item.work_orders));

  return <>
    <div className="stats-grid data-stats reports-stats">
      <Stat label="Assets in inventory" value={snapshot.summary.assets} icon={Package} tone="blue"/>
      <Stat label="Requests in period" value={snapshot.summary.requests} icon={ClipboardList} tone="green"/>
      <Stat label="Incidents in period" value={snapshot.summary.incidents} icon={AlertTriangle} tone="red"/>
      <Stat label="Work orders scheduled" value={snapshot.summary.work_orders} icon={Wrench} tone="orange"/>
    </div>
    <div className="reports-grid">
      <section className="panel data-panel report-trend-panel">
        <div className="panel-heading"><div className="panel-title"><h2>Daily operational activity</h2></div><span className="report-period">{snapshot.start_date} – {snapshot.end_date}</span></div>
        <div className="report-trend-scroll">
          {!snapshot.daily_trend.some(item => item.requests || item.incidents || item.work_orders) ? <p className="empty-state">No activity recorded for this period.</p> : <table className="report-trend-table">
            <thead><tr><th>Date</th><th>Requests</th><th>Incidents</th><th>Work orders</th></tr></thead>
            <tbody>{snapshot.daily_trend.map(item => <tr key={item.date}>
              <td>{new Date(`${item.date}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</td>
              <td><ReportTrendValue value={item.requests} maximum={maxRequests} tone="blue"/></td>
              <td><ReportTrendValue value={item.incidents} maximum={maxIncidents} tone="red"/></td>
              <td><ReportTrendValue value={item.work_orders} maximum={maxWorkOrders} tone="orange"/></td>
            </tr>)}</tbody>
          </table>}
        </div>
      </section>
      <ReportBreakdown title="Current asset status" items={snapshot.asset_status}/>
      <ReportBreakdown title="Service request status" items={snapshot.request_status.filter(item => item.count > 0)}/>
      <ReportBreakdown title="Incident severity" items={snapshot.incident_severity}/>
      <ReportBreakdown title="Work order status" items={snapshot.work_order_status}/>
    </div>
    <p className="report-footnote">Open requests: {snapshot.summary.open_requests} · Open incidents: {snapshot.summary.open_incidents} · Completed work orders: {snapshot.summary.completed_work_orders}. Generated {new Date(snapshot.generated_at).toLocaleString()}.</p>
  </>;
}

function ReportBreakdown({ title, items }: { title: string; items: ReportCount[] }) {
  const maximum = Math.max(1, ...items.map(item => item.count));
  return <section className="panel data-panel report-breakdown">
    <div className="panel-heading"><div className="panel-title"><h2>{title}</h2></div></div>
    <div className="report-breakdown-list">{items.map(item => <div key={item.label}>
      <div className="report-breakdown-label"><span>{item.label.replaceAll("_", " ")}</span><strong>{item.count}</strong></div>
      <span className="report-breakdown-track"><i style={{ width: `${item.count / maximum * 100}%` }}/></span>
    </div>)}</div>
    {!items.length && <p className="empty-state">No records in this period.</p>}
  </section>;
}

function ReportTrendValue({ value, maximum, tone }: { value: number; maximum: number; tone: string }) {
  return <div className={`report-trend-value ${tone}`}><span><i style={{ width: `${value / maximum * 100}%` }}/></span><strong>{value}</strong></div>;
}

function AIInsightsView({ filters, sites, consent, result, loading, onFiltersChange, onConsentChange, onSubmit }: {
  filters: ReturnType<typeof defaultReportFilters>;
  sites: LocationOption[];
  consent: boolean;
  result: GeneratedAIInsights | null;
  loading: boolean;
  onFiltersChange: (filters: ReturnType<typeof defaultReportFilters>) => void;
  onConsentChange: (consent: boolean) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  function updateFilter(field: keyof typeof filters, value: string) {
    onFiltersChange({ ...filters, [field]: value });
  }

  return <>
    <form className="panel report-controls ai-insights-controls" onSubmit={onSubmit}>
      <label>From<input type="date" required value={filters.start_date} onChange={event => updateFilter("start_date", event.target.value)}/></label>
      <label>To<input type="date" required value={filters.end_date} onChange={event => updateFilter("end_date", event.target.value)}/></label>
      <label>Site<select value={filters.site_id} onChange={event => updateFilter("site_id", event.target.value)}><option value="">All accessible sites</option>{sites.map(site => <option key={site.id} value={site.id}>{site.name}</option>)}</select></label>
      <label className="ai-consent"><input type="checkbox" required checked={consent} onChange={event => onConsentChange(event.target.checked)}/><span>I agree to send aggregated operational counts to OpenAI for this analysis.</span></label>
      <div className="ai-controls-actions"><button type="submit" className="primary-button" disabled={loading || !consent}><CircleHelp size={15}/>{loading ? "Generating..." : "Generate insights"}</button></div>
      <p className="ai-privacy-note">Only totals and daily counts are sent—no names, descriptions, notes, or record IDs. Generation is on demand and API response storage is disabled; OpenAI’s applicable data-handling policies still apply.</p>
    </form>
    {loading && <div className="panel table-state"><LoaderCircle className="spin" size={19}/>Analyzing aggregated operational data...</div>}
    {result && !loading && <section className="panel data-panel ai-results">
      <div className="panel-heading ai-results-heading"><div className="panel-title"><h2>Operational insights</h2></div><span>{result.start_date} – {result.end_date} · {result.model}</span></div>
      {result.insights.length ? <div className="ai-insight-list">{result.insights.map((insight, index) => <AIInsightCard key={`${insight.category}-${index}`} insight={insight}/>)}</div> : <Empty title="No strong signals in this period" text="The available counts did not support a reliable operational recommendation."/>}
      <p className="ai-results-footnote">AI-generated guidance can be incomplete. Verify evidence and follow your organization’s safety procedures. Generated {new Date(result.generated_at).toLocaleString()}.</p>
    </section>}
    {!result && !loading && <Empty title="Generate operational insights" text="Choose a date range and site, review the data-sharing notice, then generate an evidence-backed summary from your authorized operational totals."/>}
  </>;
}

function AIInsightCard({ insight }: { insight: AIInsight }) {
  return <article className={`ai-insight-card insight-${insight.severity}`}>
    <div className="ai-insight-title"><span className="ai-insight-category">{insight.category.replaceAll("_", " ")}</span><span className={`ai-insight-severity ${insight.severity}`}>{insight.severity}</span></div>
    <h3>{insight.title}</h3>
    <div className="ai-evidence"><strong>Evidence</strong><ul>{insight.evidence.map((item, index) => <li key={index}>{item}</li>)}</ul></div>
    <p><strong>Suggested action:</strong> {insight.recommendation}</p>
  </article>;
}

function DataTable({ children, loading, empty }: { children: ReactNode; loading: boolean; empty: boolean }) {
  if (loading) return <div className="table-state"><LoaderCircle className="spin" size={19}/>Loading live data...</div>;
  return <div className="table-content">{empty ? <p className="empty-state">No records to display.</p> : children}</div>;
}

function Stat({ label, value, icon: Icon, tone }: { label: string; value: string | number; icon: typeof Home; tone: string }) {
  return <div className={`stat-card ${tone}`}><div className="stat-icon"><Icon/></div><div><span>{label}</span><strong>{value}</strong></div></div>;
}

function Badge({ value }: { value: string }) {
  return <span className={`status status-${value.replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>;
}

function Empty({ title, text }: { title: string; text: string }) {
  return <div className="empty-workspace"><CircleHelp size={25}/><strong>{title}</strong><span>{text}</span></div>;
}

function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return <div className="modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}><section className="modal" role="dialog" aria-modal="true" aria-label={title}><div className="modal-heading"><h2>{title}</h2><button className="icon-button modal-close" onClick={onClose} aria-label="Close"><X size={19}/></button></div>{children}</section></div>;
}

export default App;