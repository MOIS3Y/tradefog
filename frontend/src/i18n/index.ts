import { createI18n } from "vue-i18n";

const messages = {
  en: {
    common: {
      retry: "Try again",
      signOut: "Sign out",
      home: "Return home",
      language: "Change language",
      menu: "Menu",
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
      next: "Next stage",
    },
    dashboard: {
      eyebrow: "Decision desk",
      greeting: "Good to see you, {name}.",
      lead: "A deliberate trade begins before the order reaches the market.",
      emptyTitle: "Build your trading context",
      emptyBody:
        "Start with the shared catalog, then connect a venue, capital, and strategy. These workspaces arrive in the next implementation stages.",
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
      next: "Следующий этап",
    },
    dashboard: {
      eyebrow: "Рабочий стол",
      greeting: "Рады видеть вас, {name}.",
      lead: "Осознанная сделка начинается до отправки заявки на рынок.",
      emptyTitle: "Соберите торговый контекст",
      emptyBody:
        "Начните с общего каталога, затем свяжите площадку, капитал и стратегию. Эти разделы появятся на следующих этапах.",
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
