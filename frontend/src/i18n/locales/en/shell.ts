/** EN translations: shell. */
export default {
  nav: {
    overview: "Overview",
    catalog: "Catalog",
    profiles: "Profiles",
    trades: "Trades",
    analytics: "Analytics",
  },
  dashboard: {
    eyebrow: "Decision desk",
    greeting: "Good to see you, {name}.",
    lead: "Your journal overview and trading workspace setup.",
    emptyTitle: "Build your trading context",
    emptyBody:
      "Create a Bybit or manual profile, set up its instruments, then fund your virtual wallet and allocate capital to a strategy.",
    connection: "API connected",
    staff: "Staff access",
    user: "Personal journal",
    sequence: "First-use sequence",
    stepCatalog: "Reference catalog",
    stepProfile: "Profile and wallet",
    stepStrategy: "Risk strategy",
    stepTrade: "First trade",
    discipline: "Risk discipline",
    maxim: "You cannot control the market. You can control how much you risk.",
  },
  notFound: {
    title: "Outside the journal",
    body: "The page you requested does not exist.",
  },
  workspaceEmpty: {
    profiles: {
      title: "You have no trading profiles yet",
      description:
        "Create a Bybit or manual profile to set up instruments, virtual capital and strategies.",
    },
    filteredProfiles: {
      title: "No profiles match these filters",
      description:
        "Change the search or show all profiles, including archived ones.",
      action: "Show all profiles",
    },
    start: {
      title: "Start with a trading profile",
      description:
        "Create a profile, add an instrument and set up virtual capital to prepare your first trade.",
      action: "Go to profiles",
    },
    trades: {
      title: "You have no trades yet",
      description:
        "Create your first trade to prepare an entry plan and record your decision.",
      action: "Create trade",
    },
    archivedProfiles: {
      title: "No active trading profiles",
      description:
        "Create a profile or restore an archived one to prepare a trade.",
      action: "Go to profiles",
    },
    filteredTrades: {
      description: "Change the search conditions or reset the filters.",
    },
  },
  pageDescriptions: {
    catalog: "Assets, trading pairs and execution venues.",
    profiles: "Wallets, strategies and capital for each trading profile.",
    trades: "Find trades, compare results and track reviews.",
    newTrade: "Choose a profile, strategy and instrument for your trade.",
    trade: "Position plan, risk, execution and trade review.",
  },
} as const;
