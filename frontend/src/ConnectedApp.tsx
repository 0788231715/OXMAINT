import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  AlertTriangle, ArrowUpRight, BarChart3, Building2, CheckCircle2,
  ChevronDown, CircleHelp, ClipboardList, Home, LoaderCircle, Menu,
  Moon, Package, Plus, RefreshCw, Search, Settings, Shield, Sun,
  Truck, Users, Wrench, X
} from "lucide-react";
import { api, ApiError, type Asset, type AssetCategory, type LocationOption, type Organization, type Page, type ServiceRequest, type User } from "./api";

const navItems = [
  ["Dashboard", Home, true],
  ["Service Requests", ClipboardList, true],
  ["Assets & Equipment", Truck, true],
  ["Asset Categories", Package, true],
  ["Incidents", AlertTriangle, false],
  ["Maintenance", Wrench, false],
  ["Coordination", Users, false],
  ["Reports & Analytics", BarChart3, false],
  ["AI Insights", CircleHelp, false],
  ["Operations Map", Building2, false],
  ["Synchronization", RefreshCw, false],
  ["Settings", Settings, false],
  ["Help & Support", CircleHelp, false]
] as const;

const transitions: Record<string, string[]> = {
  assigned: ["in_progress", "waiting", "cancelled"],
  in_progress: ["waiting", "completed", "cancelled"],
  waiting: ["in_progress", "cancelled"],
  completed: ["closed"]
};

function message(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed.";
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
  const [sites, setSites] = useState<LocationOption[]>([]);
  const [departments, setDepartments] = useState<LocationOption[]>([]);
  const [counts, setCounts] = useState({ inService: 0, maintenance: 0, outOfService: 0, retired: 0, submitted: 0, underReview: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [dark, setDark] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [modal, setModal] = useState("");
  const [actionRequest, setActionRequest] = useState<ServiceRequest | null>(null);
  const [actionKind, setActionKind] = useState("");
  const [actionValue, setActionValue] = useState("");
  const [actionUser, setActionUser] = useState("");
  const [submitting, setSubmitting] = useState(false);

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
      setOrganizationId(selected => orgs.some(org => org.id === selected) ? selected : orgs[0]?.id || "");
    }).catch(err => {
      if (!current) return;
      setLoginError(message(err));
      sessionStorage.removeItem("oxmaint-token");
      setToken("");
    }).finally(() => current && setAuthLoading(false));
    return () => { current = false; };
  }, [token]);

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

  const org = organizations.find(item => item.id === organizationId);
  const assets = useMemo(() => (assetPage?.items || []).filter(item => `${item.asset_tag} ${item.name} ${item.status} ${item.criticality}`.toLowerCase().includes(query.toLowerCase())), [assetPage, query]);
  const requests = useMemo(() => (requestPage?.items || []).filter(item => `${item.request_number} ${item.title} ${item.status} ${item.priority}`.toLowerCase().includes(query.toLowerCase())), [requestPage, query]);

  async function login(email: string, password: string) {
    setLoginLoading(true);
    setLoginError("");
    try {
      const result = await api.login(email, password);
      sessionStorage.setItem("oxmaint-token", result.access_token);
      setToken(result.access_token);
    } catch (err) { setLoginError(message(err)); }
    finally { setLoginLoading(false); }
  }

  function signOut() {
    sessionStorage.removeItem("oxmaint-token");
    setToken("");
    setUser(null);
    setOrganizations([]);
    setOrganizationId("");
    setAssetPage(null);
    setCategoryPage(null);
    setRequestPage(null);
  }

  async function submitForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !organizationId) return;
    setSubmitting(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const body: Record<string, unknown> = Object.fromEntries(form.entries());
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
        await api.createServiceRequest(token, organizationId, body);
      } else if (modal === "user") {
        const siteIds = form.getAll("site_ids").map(String);
        if (!siteIds.length) throw new Error("Select at least one site.");
        body.site_ids = siteIds;
        body.department_ids = form.getAll("department_ids").map(String);
        await api.registerTechnician(token, organizationId, body);
      }
      setModal("");
      setNotice(modal === "asset" ? "Asset created." : modal === "category" ? "Category created." : modal === "request" ? "Service request submitted." : "Maintenance technician registered.");
      setReload(value => value + 1);
    } catch (err) { setError(message(err)); }
    finally { setSubmitting(false); }
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
      await api.requestAction(token, organizationId, actionRequest.id, actionKind, body);
      setActionRequest(null);
      setNotice(`${actionKind[0]?.toUpperCase()}${actionKind.slice(1)} completed.`);
      setReload(value => value + 1);
    } catch (err) { setError(message(err)); }
    finally { setSubmitting(false); }
  }

  if (authLoading) return <div className="full-loading"><LoaderCircle className="spin"/>Loading your workspace</div>;
  if (!token || !user) return <Login onSubmit={login} busy={loginLoading} error={loginError}/>;

  const activeSectionAvailable = navItems.find(item => item[0] === active)?.[2] ?? false;
  const openRequests = counts.submitted + counts.underReview;

  return <div className={`app-shell ${dark ? "dark" : ""}`}>
    <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
      <div className="brand"><div className="brand-mark"><Shield size={27}/></div><div><strong>OxMaint</strong><span>Operations · Support · Resilience</span></div><button className="mobile-close" onClick={() => setSidebarOpen(false)} aria-label="Close navigation"><X size={19}/></button></div>
      <nav className="side-nav" aria-label="Main navigation">{navItems.map(([label, Icon, available]) => <button key={label} className={`nav-item ${active === label ? "active" : ""} ${available ? "" : "nav-unavailable"}`} title={available ? label : `${label} API is not available yet`} onClick={() => { setActive(label); setSidebarOpen(false); }}><Icon size={18}/><span>{label}</span>{!available && <small>Later</small>}</button>)}</nav>
      <div className="system-card"><div className="system-check"><CheckCircle2 size={19}/></div><div><strong>{loading ? "Refreshing data" : error ? "Connection needs attention" : "Connected to backend"}</strong><span>{org?.name || "Choose an organization"}</span></div></div>
      <div className="theme-switch"><Moon size={16}/><button aria-label="Toggle theme" onClick={() => setDark(!dark)} className={`switch ${dark ? "on" : ""}`}><span/></button><Sun size={16}/></div>
      <div className="sidebar-footer">OxMaint Platform <span>v1.0.0</span></div>
    </aside>
    {sidebarOpen && <button className="scrim" onClick={() => setSidebarOpen(false)} aria-label="Close menu"/>}
    <div className="main-area">
      <header className="topbar"><button className="mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="Open menu"><Menu size={21}/></button><div className="search-wrap"><Search size={18}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search assets and service requests..."/></div><div className="topbar-right"><div className="online"><span/>API connected</div><label className="organization-select"><Building2 size={16}/><select aria-label="Organization" value={organizationId} onChange={event => setOrganizationId(event.target.value)}><option value="">No organization</option>{organizations.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select><ChevronDown size={14}/></label><div className="notification-wrap"><button className="icon-button" onClick={() => setNotificationsOpen(!notificationsOpen)} aria-label="Request notifications"><ClipboardList size={19}/><b>{openRequests}</b></button>{notificationsOpen && <div className="notification-popover"><strong>Service requests</strong><p>{counts.submitted} submitted</p><p>{counts.underReview} under review</p></div>}</div><button className="user-menu" onClick={signOut}><span className="user-avatar">{user.display_name.slice(0, 1).toUpperCase()}</span><span><strong>{user.display_name}</strong><small>{user.is_system_admin ? "System Administrator · Sign out" : "Sign out"}</small></span><ChevronDown size={15}/></button></div></header>
      <main className="content">
        <div className="page-heading"><div className="heading-left"><div className="heading-icon"><Shield size={24}/></div><div><h1>{active === "Dashboard" ? "Operations Dashboard" : active}</h1><p>{org ? `${org.name} · Live database data` : "Select an organization"}</p></div></div><div className="heading-tools"><button className="refresh-button" onClick={() => setReload(value => value + 1)} disabled={loading} aria-label="Refresh data"><RefreshCw size={17} className={loading ? "spin" : ""}/></button>{org?.can_register_users && <button className="secondary-button" onClick={() => setModal("user")}><Users size={15}/>Register user</button>}{active === "Assets & Equipment" && <button className="primary-button" onClick={() => setModal("asset")}><Plus size={16}/>New Asset</button>}{active === "Asset Categories" && <button className="primary-button" onClick={() => setModal("category")}><Plus size={16}/>New Category</button>}{active === "Service Requests" && <button className="primary-button" onClick={() => setModal("request")}><Plus size={16}/>New Request</button>}</div></div>
        {notice && <div className="notice"><CheckCircle2 size={16}/>{notice}<button onClick={() => setNotice("")} aria-label="Dismiss"><X size={15}/></button></div>}
        {error && <div className="form-error page-error" role="alert">{error}<button onClick={() => setError("")} aria-label="Dismiss error"><X size={15}/></button></div>}
        {!organizationId && <Empty title="No organization access" text="Your account has no active organization assignment. Ask an administrator to grant access."/>}
        {organizationId && !activeSectionAvailable && <Empty title={`${active} is not connected yet`} text="The backend currently supports assets, asset categories, service requests, and organization locations. This section will become live when its API is available."/>}
        {organizationId && active === "Dashboard" && <Dashboard assetPage={assetPage} requestPage={requestPage} counts={counts} loading={loading} onOpen={setActive}/>}
        {organizationId && active === "Assets & Equipment" && <AssetsView assets={assets} total={assetPage?.total || 0} loading={loading}/>}
        {organizationId && active === "Asset Categories" && <CategoriesView categories={categoryPage?.items || []} loading={loading}/>}
        {organizationId && active === "Service Requests" && <RequestsView requests={requests} total={requestPage?.total || 0} loading={loading} onAction={(request, action) => { setActionRequest(request); setActionKind(action); setActionValue(""); setActionUser(""); }}/>}
      </main>
    </div>

    {modal && <Modal title={modal === "asset" ? "Create asset" : modal === "category" ? "Create asset category" : modal === "request" ? "Submit service request" : "Register maintenance technician"} onClose={() => setModal("")}><form className="data-form" onSubmit={submitForm}>
      {modal === "asset" && <><label>Asset tag<input name="asset_tag" required maxLength={100}/></label><label>Name<input name="name" required maxLength={200}/></label><label>Category<select name="category_id" required defaultValue=""><option value="" disabled>Select category</option>{(categoryPage?.items || []).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Site<select name="site_id" required defaultValue=""><option value="" disabled>Select accessible site</option>{sites.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Department<select name="department_id" defaultValue=""><option value="">No department</option>{departments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Status<select name="status"><option value="in_service">In service</option><option value="under_maintenance">Under maintenance</option><option value="out_of_service">Out of service</option><option value="retired">Retired</option></select></label><label>Criticality<select name="criticality"><option>low</option><option selected>medium</option><option>high</option><option>critical</option></select></label></>}
      {modal === "category" && <><label>Name<input name="name" required maxLength={150}/></label><label>Code<input name="code" required maxLength={80}/></label><label>Description<textarea name="description"/></label></>}
      {modal === "request" && <><label>Title<input name="title" required minLength={3} maxLength={200}/></label><label>Description<textarea name="description" required minLength={5} maxLength={10000}/></label><label>Site<select name="site_id" required defaultValue=""><option value="" disabled>Select accessible site</option>{sites.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Department<select name="department_id" defaultValue=""><option value="">No department</option>{departments.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Related asset<select name="asset_id" defaultValue=""><option value="">No asset</option>{(assetPage?.items || []).map(item => <option key={item.id} value={item.id}>{item.asset_tag} · {item.name}</option>)}</select></label><label>Category<input name="category" required minLength={2} maxLength={50} defaultValue="general"/></label><label>Priority<select name="priority"><option>low</option><option>normal</option><option>high</option><option>urgent</option></select></label><label className="checkbox-label"><input name="safety_critical" type="checkbox"/>Safety critical</label></>}
      {modal === "user" && <><label>Full name<input name="display_name" required maxLength={150}/></label><label>Email<input name="email" type="email" required maxLength={320}/></label><label>Initial password<input name="initial_password" type="password" required minLength={12} maxLength={128} autoComplete="new-password"/><small>The technician can use this password to sign in.</small></label><fieldset className="location-checks"><legend>Sites <span>Choose at least one</span></legend>{sites.map(site => <label key={site.id}><input type="checkbox" name="site_ids" value={site.id}/>{site.name}</label>)}</fieldset>{departments.length > 0 && <fieldset className="location-checks"><legend>Departments <span>Optional</span></legend>{departments.map(department => <label key={department.id}><input type="checkbox" name="department_ids" value={department.id}/>{department.name}</label>)}</fieldset>}<p className="modal-description">Role: Maintenance Technician</p></>}
      <div className="form-actions"><button type="button" className="secondary-button" onClick={() => setModal("")}>Cancel</button><button className="primary-button" disabled={submitting}>{submitting ? "Saving" : "Submit"}</button></div>
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