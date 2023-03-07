import { addMessages, getLocaleFromNavigator, locale, init, _, time, date, number } from 'svelte-i18n';
import { website } from "../config";
import { derived } from 'svelte/store';

// Add all ./xx.json localizations here
import ar from './ar.json';
import en from './en.json';
addMessages('ar', ar);
addMessages('en', en);
let l17ns = { "ar": ar, "en": en };
let available_locales = ["ar", "en"];
let actual_locales = available_locales.filter((x) => x in website.languages);


function switchLocale(_locale) {
  if (!(_locale in website.languages)) {
    _locale = "en";
  }
  localStorage.setItem("preferred_locale", JSON.stringify(_locale));
  locale.set(_locale);
}

function getPreferredLocale() {
  if (localStorage.getItem("preferred_locale")) {
    return JSON.parse(localStorage.getItem("preferred_locale"));
  }

  let fallback = null;
  let _locale = getLocaleFromNavigator();
  let _locale_found = false;

  for (const key in website.languages) {
    // Assign first locale as fallback
    if (fallback == null) {
      fallback = key;
    }
    // Match User locale from browser to existing locale.
    if (!_locale_found && _locale.startsWith(key)) {
      _locale = key;
      _locale_found = true;
    }
  }

  if (!_locale_found) {
    _locale = fallback;
  }

  if (!_locale) {
    _locale = "en";
  }

  localStorage.setItem("preferred_locale", JSON.stringify(_locale));
  return _locale;
}

function setupI18n() {

  let _locale = getPreferredLocale();

  if (!(_locale in l17ns)) {
    _locale = "en";
  }

  init({
    initialLocale: _locale,
    fallbackLocale: "en"
  });
}

const rtl = ["ar", "fa", "ur", "kd"]; // Arabic, Farsi, Urdu, Kurdish

const dir = derived(locale, $locale => rtl.indexOf($locale) >= 0 ? 'rtl' : 'ltr');
const isLocaleLoaded = derived(locale, $locale => typeof $locale === 'string');

export { _, dir, setupI18n, time, date, number, locale, isLocaleLoaded, switchLocale, available_locales, actual_locales };
