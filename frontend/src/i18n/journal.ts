/** Journal navigation and shared paginated collection copy. */
export const journalMessages = {
  en: {
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
    tradeTimes: {
      label: "Trade events · local time",
      created_at: "Created",
      submitted_at: "Submitted",
      opened_at: "Opened",
      closed_at: "Closed",
      cancelled_at: "Cancelled",
    },
    pagination: {
      label: "Pages",
      summary: "Page {page} of {pages} · {total} records",
      size: "Per page",
      previous: "Previous",
      next: "Next",
      more: "Load more",
      loading: "Loading…",
      retry: "Retry loading",
    },
    journal: {
      title: "Trades",
      detail: "Trade #{id}",
      back: "Trade list",
      pnl: "Net P&L",
      reviewLabel: "Review",
      allProfiles: "All profiles",
      allStrategies: "All strategies",
      allDirections: "Direction",
      emptyBody: "Adjust the filters or create a new trade.",
      setup: "Configure a profile, wallet and strategy to begin.",
      review: {
        all: "All reviews",
        reviewed: "Reviewed",
        unreviewed: "Awaiting review",
      },
      rating: { all: "All ratings", rated: "Rated", unrated: "Not rated" },
    },
  },
  ru: {
    workspaceEmpty: {
      profiles: {
        title: "У вас пока нет торговых профилей",
        description:
          "Создайте профиль Bybit или ручной площадки, чтобы настроить инструменты, виртуальный капитал и стратегии.",
      },
      filteredProfiles: {
        title: "По этим фильтрам профилей нет",
        description:
          "Измените поиск или покажите все профили, включая архивные.",
        action: "Показать все профили",
      },
      start: {
        title: "Начните с торгового профиля",
        description:
          "Создайте профиль, добавьте инструмент и настройте виртуальный капитал, чтобы подготовить первую сделку.",
        action: "Перейти в профили",
      },
      trades: {
        title: "У вас пока нет сделок",
        description:
          "Создайте первую сделку, чтобы подготовить план входа и зафиксировать решение.",
        action: "Создать сделку",
      },
      archivedProfiles: {
        title: "Нет активных торговых профилей",
        description:
          "Создайте профиль или восстановите архивный, чтобы подготовить сделку.",
        action: "Перейти в профили",
      },
      filteredTrades: {
        description: "Измените условия поиска или сбросьте фильтры.",
      },
    },
    pageDescriptions: {
      catalog: "Ресурсы, торговые пары и площадки исполнения.",
      profiles: "Кошельки, стратегии и капитал каждого торгового профиля.",
      trades: "Поиск сделок, сравнение результатов и контроль разбора.",
      newTrade: "Выберите профиль, стратегию и инструмент для сделки.",
      trade: "План позиции, риск, исполнение и разбор сделки.",
    },
    tradeTimes: {
      label: "События сделки · местное время",
      created_at: "Создана",
      submitted_at: "Отправлена",
      opened_at: "Открыта",
      closed_at: "Закрыта",
      cancelled_at: "Отменена",
    },
    pagination: {
      label: "Страницы",
      summary: "Страница {page} из {pages} · записей: {total}",
      size: "На странице",
      previous: "Назад",
      next: "Далее",
      more: "Загрузить ещё",
      loading: "Загрузка…",
      retry: "Повторить загрузку",
    },
    journal: {
      title: "Сделки",
      detail: "Сделка №{id}",
      back: "Список сделок",
      pnl: "Чистый P&L",
      reviewLabel: "Разбор",
      allProfiles: "Все профили",
      allStrategies: "Все стратегии",
      allDirections: "Направление",
      emptyBody: "Измените фильтры или создайте новую сделку.",
      setup: "Настройте профиль, кошелёк и стратегию для начала работы.",
      review: {
        all: "Любой разбор",
        reviewed: "Разобрана",
        unreviewed: "Ожидает разбора",
      },
      rating: {
        all: "Любая оценка",
        rated: "С оценкой",
        unrated: "Без оценки",
      },
    },
  },
};
