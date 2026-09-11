/** EN translations: catalog. */
export default {
  catalog: {
    title: "Market catalog",
    sequence: "Catalog setup sequence",
    venues: "Venues",
    searchAssets: "Search symbol or name",
    searchPairs: "Search market or asset",
    allTypes: "All types",
    reset: "Reset",
    noResults: "No records match these filters.",
    noOptions: "No matching assets",
    loadingAssets: "Loading assets",
    loadingPairs: "Loading trading pairs",
    loadFailed: "The catalog could not be loaded",
    actions: "Actions",
    edit: "Edit",
    delete: "Delete",
    saveChanges: "Save changes",
    types: {
      crypto: "Crypto",
      fiat: "Fiat",
      equity: "Equity",
    },
    errors: {
      unavailable: "Check the API connection and try again.",
      validation: "Check the entered values and try again.",
      assetConflict:
        "This symbol already exists or the asset identity is already in use.",
      pairConflict:
        "This pair already exists or its identity is already in use.",
      assetInUse:
        "This asset is used by a pair, instrument, or wallet capability and cannot be deleted.",
      pairInUse:
        "This pair is used by a venue instrument and cannot be deleted.",
    },
    asset: {
      title: "Assets",
      description:
        "Assets are the currencies, cryptocurrencies, and equities used to build markets.",
      create: "Add asset",
      createFirst: "Create first asset",
      addRequired: "Add required assets",
      goToAssets: "Go to assets",
      symbol: "Symbol",
      name: "Name",
      type: "Type",
      emptyTitle: "No assets yet",
      createTitle: "New asset",
      editTitle: "Edit asset",
      formDescription:
        "Use the canonical market symbol. It will be normalized to uppercase.",
      symbolHint: "Up to 32 characters, for example BTC or USD.",
      namePlaceholder: "Bitcoin",
      created: "Asset created",
      saved: "Asset updated",
      deleted: "Asset deleted",
      saveFailed: "Asset was not saved",
      deleteFailed: "Asset was not deleted",
      deleteTitle: "Delete asset?",
      deleteBody:
        "{symbol} will be permanently removed if it has no catalog references.",
    },
    pair: {
      title: "Trading pairs",
      description:
        "A trading pair joins a base asset and quote asset into one market.",
      create: "Add pair",
      createFirst: "Create first pair",
      market: "Market",
      typeRelation: "Type relation",
      base: "Base asset",
      quote: "Quote asset",
      emptyTitle: "No trading pairs yet",
      createTitle: "New trading pair",
      editTitle: "Edit trading pair",
      formDescription:
        "Choose two different assets. The BASE/QUOTE symbol is generated automatically.",
      selectBase: "Search base asset",
      selectQuote: "Search quote asset",
      selectBaseFirst: "Select the base asset first.",
      baseHint: "The asset being priced.",
      quoteHint: "The asset used to express the price.",
      created: "Trading pair created",
      saved: "Trading pair updated",
      deleted: "Trading pair deleted",
      saveFailed: "Trading pair was not saved",
      deleteFailed: "Trading pair was not deleted",
      deleteTitle: "Delete trading pair?",
      deleteBody:
        "{symbol} will be permanently removed if no venue instrument uses it.",
    },
  },
} as const;
