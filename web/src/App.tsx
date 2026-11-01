import { DataProvider, ConnectionBar, ConnectedPage } from "./connected"
import { useState, type ReactNode } from "react"

type IconName = "overview" | "farmers" | "crop" | "soil" | "data" | "query" | "advisory" | "alert" | "report" | "staff" | "settings" | "home" | "weather" | "profile" | "menu" | "close" | "refresh" | "chevron" | "leaf" | "search" | "plus" | "headphones" | "language" | "shield" | "plug"

const paths: Record<IconName, ReactNode> = {
  overview: (
    <>
      <path d="M4 13h6V4H4v9Zm0 7h6v-3H4v3Zm10 0h6v-9h-6v9Zm0-13h6V4h-6v3Z" />
    </>
  ),
  farmers: (
    <>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
    </>
  ),
  crop: (
    <>
      <path d="M12 22V8M5 12c4.5 0 7-2.5 7-7-4.5 0-7 2.5-7 7Zm14 5c-4.5 0-7-2.5-7-7 4.5 0 7 2.5 7 7Z" />
    </>
  ),
  soil: (
    <>
      <path d="M3 7c3 0 3 2 6 2s3-2 6-2 3 2 6 2M3 13c3 0 3 2 6 2s3-2 6-2 3 2 6 2M3 19h18" />
    </>
  ),
  data: (
    <>
      <path d="M4 19V9M10 19V5M16 19v-7M22 19V3" />
    </>
  ),
  query: (
    <>
      <path d="M21 15a4 4 0 0 1-4 4H8l-5 3v-5a7 7 0 0 1-1-4V8a4 4 0 0 1 4-4h11a4 4 0 0 1 4 4v7Z" />
    </>
  ),
  advisory: (
    <>
      <path d="M9 18h6M10 22h4M8.5 14.5A7 7 0 1 1 15.5 14.5c-.9.7-1.5 1.6-1.5 2.5h-4c0-.9-.6-1.8-1.5-2.5Z" />
    </>
  ),
  alert: (
    <>
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4" />
    </>
  ),
  report: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z" />
      <path d="M14 2v6h6M8 13h8M8 17h8" />
    </>
  ),
  staff: (
    <>
      <path d="M12 15a6 6 0 0 0-6 6M12 15a6 6 0 0 1 6 6M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM19 8h4M21 6v4" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
    </>
  ),
  home: (
    <>
      <path d="m3 11 9-8 9 8v10h-6v-6H9v6H3V11Z" />
    </>
  ),
  weather: (
    <>
      <path d="M17.5 19H7a5 5 0 1 1 1.3-9.8A7 7 0 0 1 21 13a4 4 0 0 1-3.5 6Z" />
    </>
  ),
  profile: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 22a8 8 0 0 1 16 0" />
    </>
  ),
  menu: (
    <>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </>
  ),
  close: (
    <>
      <path d="m6 6 12 12M18 6 6 18" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 6v5h-5M4 18v-5h5M6.1 9a7 7 0 0 1 11.6-2.6L20 9M4 15l2.3 2.6A7 7 0 0 0 18 15" />
    </>
  ),
  chevron: (
    <>
      <path d="m9 18 6-6-6-6" />
    </>
  ),
  leaf: (
    <>
      <path d="M20.5 3.5C13 3 7.5 5.5 5 10c-2 3.5-.5 7 2 8.5 3 1.8 7 .8 9-2.5 2.2-3.7 1.7-7.8 4.5-12.5Z" />
      <path d="M4 21c2-6 6-10 12-13" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-4-4" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5v14M5 12h14" />
    </>
  ),
  headphones: (
    <>
      <path d="M4 14v-2a8 8 0 0 1 16 0v2M4 14h3v7H4a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2ZM20 14h-3v7h3a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2Z" />
    </>
  ),
  language: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18" />
    </>
  ),
  shield: (
    <>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  plug: (
    <>
      <path d="M12 22v-5M9 8V2M15 8V2M7 8h10v3a5 5 0 0 1-10 0V8Z" />
    </>
  ),
}

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  )
}

const staffNavigation: {
  group: string
  items: { label: string; icon: IconName }[]
}[] = [
  {
    group: "Workspace",
    items: [
      { label: "Overview", icon: "overview" },
      { label: "Farmers", icon: "farmers" },
      { label: "Crop Monitoring", icon: "crop" },
      { label: "Soil Records", icon: "soil" },
    ],
  },
  {
    group: "Advisory",
    items: [
      { label: "Agricultural Data", icon: "data" },
      { label: "Farmer Queries", icon: "query" },
      { label: "AI Advisories", icon: "advisory" },
      { label: "Alerts & Notifications", icon: "alert" },
    ],
  },
  {
    group: "Administration",
    items: [
      { label: "Reports", icon: "report" },
      { label: "Staff Management", icon: "staff" },
      { label: "Settings", icon: "settings" },
    ],
  },
]

function Brand() {
  return (
    <div className="brand">
      <div className="brand-mark">
        <Icon name="leaf" size={22} />
      </div>
      <div>
        <strong>Kisan Saathi</strong>
        <span>Farmer Advisory</span>
      </div>
    </div>
  )
}

function Sidebar({
  open,
  active,
  onSelect,
  onClose,
}: {
  open: boolean
  active: string
  onSelect: (page: string) => void
  onClose: () => void
}) {
  return (
    <>
      {open && (
        <button
          className="sidebar-scrim"
          onClick={onClose}
          aria-label="Close navigation"
        />
      )}
      <aside className={`sidebar ${open ? "is-open" : ""}`}>
        <div className="sidebar-top">
          <Brand />
          <button
            className="icon-button sidebar-close"
            onClick={onClose}
            aria-label="Close navigation"
          >
            <Icon name="close" />
          </button>
        </div>
        <nav aria-label="Primary">
          {staffNavigation.map((section) => (
            <div className="nav-group" key={section.group}>
              <p>{section.group}</p>
              {section.items.map((item) => (
                <button
                  className={`nav-item ${
                    active === item.label ? "active" : ""
                  }`}
                  key={item.label}
                  onClick={() => {
                    onSelect(item.label)
                    onClose()
                  }}
                >
                  <Icon name={item.icon} />
                  <span>{item.label}</span>
                  {active === item.label && <Icon name="chevron" size={16} />}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-status">
          <span className="status-dot" />
          <div>
            <strong>KisanSaathi demo</strong>
            <span>Fictional farmer profiles</span>
          </div>
        </div>
      </aside>
    </>
  )
}

type UserRole = "farmer" | "staff"

function SignIn({ onContinue }: { onContinue: (role: UserRole) => void }) {
  const [role, setRole] = useState<UserRole | null>(null)
  return (
    <div className="signin-page">
      <section className="signin-brand-panel">
        <Brand />
        <div className="signin-message">
          <span className="signin-kicker">Weather-aware farmer advisory</span>
          <h1>Better field decisions, built on trustworthy data.</h1>
          <p>
            One workspace for farmer records, crop monitoring, advisory review,
            and timely risk alerts.
          </p>
        </div>
        <div className="signin-trust">
          <Icon name="shield" size={18} />
          <span>
            Explore fictional farmer profiles. Weather and prices carry source labels; agronomic rules are demonstrations.
          </span>
        </div>
      </section>
      <section className="signin-form-panel">
        <div className="signin-card">
          <div className="signin-heading">
            <span>Welcome to Kisan Saathi</span>
            <h2>How will you use Kisan Saathi?</h2>
            <p>आप किसान हैं या स्टाफ सदस्य?</p>
          </div>
          <div
            className="role-options"
            role="radiogroup"
            aria-label="Choose your role"
          >
            <button
              className={`role-card ${role === "farmer" ? "selected" : ""}`}
              onClick={() => setRole("farmer")}
              role="radio"
              aria-checked={role === "farmer"}
            >
              <span className="role-icon farmer">
                <Icon name="farmers" size={24} />
              </span>
              <span className="role-copy">
                <strong>Farmer</strong>
                <small>किसान</small>
                <em>View crops, advisories, weather, and alerts</em>
              </span>
              <span className="radio-mark" />
            </button>
            <button
              className={`role-card ${role === "staff" ? "selected" : ""}`}
              onClick={() => setRole("staff")}
              role="radio"
              aria-checked={role === "staff"}
            >
              <span className="role-icon staff">
                <Icon name="staff" size={24} />
              </span>
              <span className="role-copy">
                <strong>Staff member</strong>
                <small>स्टाफ सदस्य</small>
                <em>Manage farmers, advisories, data, and reports</em>
              </span>
              <span className="radio-mark" />
            </button>
          </div>
          <button
            className="primary-button signin-continue"
            disabled={!role}
            onClick={() => role && onContinue(role)}
          >
            Continue
            <Icon name="chevron" size={17} />
          </button>
          <p className="signin-disclaimer">
            <Icon name="shield" size={15} />
            Role selection is a preview only. Secure sign-in requires a
            connected authentication service.
          </p>
        </div>
        <div className="signin-language">
          <Icon name="language" size={16} />
          English / हिन्दी
        </div>
      </section>
    </div>
  )
}

const farmerNavigation = [
  { label: "Home", hindi: "होम", icon: "home" as IconName },
  { label: "Ask Kisan Saathi", hindi: "सवाल पूछें", icon: "query" as IconName },
  {
    label: "Weather & Mandi",
    hindi: "मौसम और मंडी",
    icon: "weather" as IconName,
  },
  { label: "My Crops", hindi: "मेरी फसलें", icon: "crop" as IconName },
  { label: "My Advisories", hindi: "मेरी सलाह", icon: "advisory" as IconName },
  { label: "Alerts", hindi: "अलर्ट", icon: "alert" as IconName },
  { label: "My Profile", hindi: "मेरी प्रोफ़ाइल", icon: "profile" as IconName },
]

function FarmerAccess({ onSignOut }: { onSignOut: () => void }) {
  const [active, setActive] = useState("Home")
  return (
    <div className="farmer-shell">
      <aside className="farmer-sidebar">
        <Brand />
        <div className="farmer-account">
          <span>
            <Icon name="profile" size={19} />
          </span>
          <div>
            <small>Farmer demo</small>
            <strong>Demo profile selector below</strong>
          </div>
        </div>
        <nav aria-label="Farmer navigation">
          {farmerNavigation.map((item) => (
            <button
              key={item.label}
              className={active === item.label ? "active" : ""}
              onClick={() => setActive(item.label)}
            >
              <Icon name={item.icon} />
              <span>
                <strong>{item.label}</strong>
                <small>{item.hindi}</small>
              </span>
            </button>
          ))}
        </nav>
        <button className="farmer-signout" onClick={onSignOut}>
          <Icon name="chevron" size={17} />
          Change role
        </button>
      </aside>
      <div className="farmer-workspace">
        <div className="farmer-topbar">
          <div className="farmer-mobile-brand">
            <Brand />
          </div>
          <div className="farmer-top-actions">
            <span className="demo-label">PUBLIC DEMO</span>
            <span className="language-button">
              <Icon name="language" size={17} />
              <span>हिन्दी / English</span>
            </span>
            <button
              className="user-avatar"
              onClick={onSignOut}
              aria-label="Change role"
            >
              KS
            </button>
          </div>
        </div>
        <main className="farmer-main"><div className="role-switch"><button className="text-button" onClick={onSignOut}>Change role</button></div><ConnectionBar />
          {active === "Home" ? (
            <ConnectedPage page="Home" onAsk={() => setActive("Ask Kisan Saathi")} />
          ) : active === "Ask Kisan Saathi" ? (
            <ConnectedPage page="Ask Kisan Saathi" />
          ) : (
            <ConnectedPage page={active} />
          )}
        </main>
        <nav
          className="farmer-bottom-nav"
          aria-label="Farmer mobile navigation"
        >
          {farmerNavigation.map((item) => (
            <button
              key={item.label}
              className={active === item.label ? "active" : ""}
              onClick={() => setActive(item.label)}
            >
              <Icon name={item.icon} size={19} />
              <span>{item.hindi}</span>
            </button>
          ))}
        </nav>
      </div>
    </div>
  )
}

function App() {
  const [role, setRole] = useState<UserRole | null>(null)
  const [active, setActive] = useState("Overview")
  const [sidebarOpen, setSidebarOpen] = useState(false)
  if (!role) return <SignIn onContinue={setRole} />
  if (role === "farmer") return <FarmerAccess onSignOut={() => setRole(null)} />
  return (
    <div className="app-shell">
      <Sidebar
        open={sidebarOpen}
        active={active}
        onSelect={setActive}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="workspace">
        <div className="topbar">
          <button
            className="icon-button mobile-menu"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
          >
            <Icon name="menu" />
          </button>
          <div className="mobile-brand">
            <Brand />
          </div>
          <div className="topbar-controls">
            <span className="language-button">
              <Icon name="language" size={17} />
              <span>English</span>
              <Icon name="chevron" size={14} />
            </span>
            <button
              className="user-avatar"
              onClick={() => setRole(null)}
              aria-label="Change role"
            >
              KS
            </button>
          </div>
        </div>
        <main><div className="role-switch"><button className="text-button" onClick={() => setRole(null)}>Change role</button></div><ConnectionBar />
          {active === "Overview" ? (
            <ConnectedPage page="Overview" />
          ) : (
            <ConnectedPage page={active} />
          )}
        </main>
        <footer>
          <span>Kisan Saathi · Weather-aware farmer advisory</span>
          <span>Demo rules · Not validated field guidance</span>
        </footer>
      </div>
    </div>
  )
}

export default function Root() { return <DataProvider><App /></DataProvider> }
