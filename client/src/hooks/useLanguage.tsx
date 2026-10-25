import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { en, LANGUAGES, type Language, type StringKey } from "../i18n/strings";

type Translate = (key: StringKey, vars?: Record<string, string | number>) => string;

const Ctx = createContext<{ lang: Language; setLang: (l: Language) => void; t: Translate } | null>(null);

function savedLanguage(): Language {
  try {
    const v = localStorage.getItem("doorstep_lang");
    if (v && v in LANGUAGES) return v as Language;
  } catch {
    // storage blocked: fall back to English
  }
  return "en";
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Language>(savedLanguage);

  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem("doorstep_lang", lang);
    } catch {
      // not fatal; the choice just won't be remembered
    }
  }, [lang]);

  const t = useCallback<Translate>(
    (key, vars) => {
      let text = LANGUAGES[lang][key] ?? en[key] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) text = text.replaceAll(`{${k}}`, String(v));
      return text;
    },
    [lang]
  );

  return <Ctx.Provider value={{ lang, setLang: setLangState, t }}>{children}</Ctx.Provider>;
}

export function useLanguage() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLanguage must be used inside LanguageProvider");
  return ctx;
}

/** Booking statuses come from the API in English; show them in the chosen language when we can. */
export function useStatusLabel() {
  const { t } = useLanguage();
  return (status: string) => {
    const key = `status.${status}` as StringKey;
    return key in en ? t(key) : status;
  };
}
