import { createI18n } from "vue-i18n";

const messages = {
  en: {
    common: {
      retry: "Try again",
      signOut: "Sign out",
      home: "Return home",
      language: "Change language",
      menu: "Menu",
      cancel: "Cancel",
      close: "Close",
      notification: "Notification",
    },
    auth: {
      eyebrow: "Private trading journal",
      title: "Return to your decision desk.",
      subtitle: "Review the process. Respect the risk. Record the outcome.",
      username: "Username",
      password: "Password",
      signIn: "Sign in",
      signingIn: "Signing in…",
      invalid: "The username or password is incorrect.",
      unavailable: "The API is unavailable. Check the backend and try again.",
      setup: "Accounts are created by an administrator from the CLI.",
    },
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
      lead: "A deliberate trade begins before the order reaches the market.",
      emptyTitle: "Build your trading context",
      emptyBody:
        "Start with assets and trading pairs in the shared catalog. Venues, capital, and strategies follow in the next workspaces.",
      connection: "API connected",
      staff: "Staff access",
      user: "Personal journal",
      sequence: "First-use sequence",
      stepCatalog: "Reference catalog",
      stepProfile: "Profile and wallet",
      stepStrategy: "Risk strategy",
      stepTrade: "First trade",
      discipline: "Risk discipline",
      maxim:
        "You cannot control the market. You can control how much you risk.",
    },
    states: {
      loading: "Loading workspace",
      empty: "Nothing here yet",
      error: "The workspace could not be loaded",
    },
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
      types: { crypto: "Crypto", fiat: "Fiat", equity: "Equity" },
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
    notFound: {
      title: "Outside the journal",
      body: "The page you requested does not exist.",
    },
  },
  ru: {
    common: {
      retry: "Повторить",
      signOut: "Выйти",
      home: "На главную",
      language: "Сменить язык",
      menu: "Меню",
      cancel: "Отмена",
      close: "Закрыть",
      notification: "Уведомление",
    },
    auth: {
      eyebrow: "Личный торговый журнал",
      title: "Вернитесь к своим решениям.",
      subtitle: "Проверяйте процесс. Соблюдайте риск. Фиксируйте результат.",
      username: "Имя пользователя",
      password: "Пароль",
      signIn: "Войти",
      signingIn: "Входим…",
      invalid: "Неверное имя пользователя или пароль.",
      unavailable: "API недоступно. Проверьте бэкенд и повторите попытку.",
      setup: "Учетные записи создаются администратором через CLI.",
    },
    nav: {
      overview: "Обзор",
      catalog: "Каталог",
      profiles: "Профили",
      trades: "Сделки",
      analytics: "Аналитика",
    },
    dashboard: {
      eyebrow: "Рабочий стол",
      greeting: "Рады видеть вас, {name}.",
      lead: "Осознанная сделка начинается до отправки заявки на рынок.",
      emptyTitle: "Соберите торговый контекст",
      emptyBody:
        "Начните с ресурсов и торговых пар в общем каталоге. Затем появятся площадки, капитал и стратегии.",
      connection: "API подключено",
      staff: "Доступ сотрудника",
      user: "Личный журнал",
      sequence: "Первичная настройка",
      stepCatalog: "Справочный каталог",
      stepProfile: "Профиль и кошелек",
      stepStrategy: "Риск-стратегия",
      stepTrade: "Первая сделка",
      discipline: "Дисциплина риска",
      maxim: "Рынок нельзя контролировать. Но можно контролировать свой риск.",
    },
    states: {
      loading: "Загружаем рабочее пространство",
      empty: "Здесь пока ничего нет",
      error: "Не удалось загрузить рабочее пространство",
    },
    catalog: {
      title: "Каталог рынков",
      sequence: "Порядок настройки каталога",
      venues: "Площадки",
      searchAssets: "Поиск по символу или названию",
      searchPairs: "Поиск по рынку или ресурсу",
      allTypes: "Все типы",
      reset: "Сбросить",
      noResults: "По этим условиям ничего не найдено.",
      noOptions: "Подходящих ресурсов нет",
      loadingAssets: "Загружаем ресурсы",
      loadingPairs: "Загружаем торговые пары",
      loadFailed: "Не удалось загрузить каталог",
      actions: "Действия",
      edit: "Изменить",
      delete: "Удалить",
      saveChanges: "Сохранить изменения",
      types: { crypto: "Криптовалюта", fiat: "Фиат", equity: "Акция" },
      errors: {
        unavailable: "Проверьте подключение к API и повторите попытку.",
        validation: "Проверьте введённые значения и повторите попытку.",
        assetConflict:
          "Такой символ уже существует либо идентификатор ресурса уже используется.",
        pairConflict:
          "Такая пара уже существует либо её идентификатор уже используется.",
        assetInUse:
          "Ресурс используется парой, инструментом или настройкой кошелька и не может быть удалён.",
        pairInUse:
          "Пара используется инструментом торговой площадки и не может быть удалена.",
      },
      asset: {
        title: "Ресурсы",
        description:
          "Ресурсы — это валюты, криптовалюты и акции, из которых формируются рынки.",
        create: "Добавить ресурс",
        createFirst: "Создать первый ресурс",
        addRequired: "Добавить ресурсы",
        goToAssets: "Перейти к ресурсам",
        symbol: "Символ",
        name: "Название",
        type: "Тип",
        emptyTitle: "Ресурсов пока нет",
        createTitle: "Новый ресурс",
        editTitle: "Изменить ресурс",
        formDescription:
          "Используйте общепринятый символ рынка. Он автоматически приводится к верхнему регистру.",
        symbolHint: "До 32 символов, например BTC или USD.",
        namePlaceholder: "Биткоин",
        created: "Ресурс создан",
        saved: "Ресурс обновлён",
        deleted: "Ресурс удалён",
        saveFailed: "Не удалось сохранить ресурс",
        deleteFailed: "Не удалось удалить ресурс",
        deleteTitle: "Удалить ресурс?",
        deleteBody:
          "{symbol} будет удалён навсегда, если на него нет ссылок в каталоге.",
      },
      pair: {
        title: "Торговые пары",
        create: "Добавить пару",
        createFirst: "Создать первую пару",
        market: "Рынок",
        typeRelation: "Отношение типов",
        description:
          "Торговая пара объединяет базовый и котируемый ресурс в один рынок.",
        base: "Базовый ресурс",
        quote: "Котируемый ресурс",
        emptyTitle: "Торговых пар пока нет",
        createTitle: "Новая торговая пара",
        editTitle: "Изменить торговую пару",
        formDescription:
          "Выберите два разных ресурса. Символ BASE/QUOTE формируется автоматически.",
        selectBase: "Найти базовый ресурс",
        selectQuote: "Найти котируемый ресурс",
        selectBaseFirst: "Сначала выберите базовый ресурс.",
        baseHint: "Ресурс, цена которого определяется.",
        quoteHint: "Ресурс, в котором выражается цена.",
        created: "Торговая пара создана",
        saved: "Торговая пара обновлена",
        deleted: "Торговая пара удалена",
        saveFailed: "Не удалось сохранить торговую пару",
        deleteFailed: "Не удалось удалить торговую пару",
        deleteTitle: "Удалить торговую пару?",
        deleteBody:
          "{symbol} будет удалена навсегда, если её не использует инструмент площадки.",
      },
    },
    notFound: {
      title: "За пределами журнала",
      body: "Запрошенной страницы не существует.",
    },
  },
} as const;

type Locale = keyof typeof messages;
const storedLocale = window.localStorage.getItem("tradefog.locale");
const locale: Locale = storedLocale === "ru" ? "ru" : "en";

export const i18n = createI18n({
  legacy: false,
  locale,
  fallbackLocale: "en",
  messages,
});

export function setLocale(locale: Locale): void {
  i18n.global.locale.value = locale;
  window.localStorage.setItem("tradefog.locale", locale);
  document.documentElement.lang = locale;
}
