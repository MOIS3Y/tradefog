import { createI18n } from "vue-i18n";
import { messages } from "./messages";

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
