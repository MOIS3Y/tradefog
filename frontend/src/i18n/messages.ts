/** Statically assembled dictionaries with unchanged global keys. */
import encommon from "./locales/en/common";
import ensettings from "./locales/en/settings";
import rusettings from "./locales/ru/settings";
import enshell from "./locales/en/shell";
import enauth from "./locales/en/auth";
import encatalog from "./locales/en/catalog";
import envenues from "./locales/en/venues";
import enprofiles from "./locales/en/profiles";
import entrades from "./locales/en/trades";
import enmarket from "./locales/en/market";
import enanalytics from "./locales/en/analytics";
import rucommon from "./locales/ru/common";
import rushell from "./locales/ru/shell";
import ruauth from "./locales/ru/auth";
import rucatalog from "./locales/ru/catalog";
import ruvenues from "./locales/ru/venues";
import ruprofiles from "./locales/ru/profiles";
import rutrades from "./locales/ru/trades";
import rumarket from "./locales/ru/market";
import ruanalytics from "./locales/ru/analytics";

export const messages = {
  en: {
    ...ensettings,
    ...encommon,
    ...enshell,
    ...enauth,
    ...encatalog,
    ...envenues,
    ...enprofiles,
    ...entrades,
    ...enmarket,
    ...enanalytics,
  },
  ru: {
    ...rusettings,
    ...rucommon,
    ...rushell,
    ...ruauth,
    ...rucatalog,
    ...ruvenues,
    ...ruprofiles,
    ...rutrades,
    ...rumarket,
    ...ruanalytics,
  },
} as const;
