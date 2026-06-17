"use client";

import * as React from "react";
import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";

// Tiny toast system: a provider mounted once in the layout, and a `useToast`
// hook returning a `toast()` function. Toasts auto-dismiss after `duration`.

type ToastVariant = "success" | "error" | "info";
interface ToastItem {
  id: number;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastCtx {
  toast: (t: { title: string; description?: string; variant?: ToastVariant; duration?: number }) => void;
}
const ToastContext = React.createContext<ToastCtx | null>(null);

const icons = {
  success: <CheckCircle2 className="h-4 w-4 text-success" />,
  error: <AlertTriangle className="h-4 w-4 text-destructive" />,
  info: <Info className="h-4 w-4 text-primary" />,
};

const accents = {
  success: "border-success/30",
  error: "border-destructive/30",
  info: "border-primary/30",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = React.useState<ToastItem[]>([]);
  const idRef = React.useRef(0);

  const remove = React.useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = React.useCallback<ToastCtx["toast"]>(
    ({ title, description, variant = "info", duration = 4500 }) => {
      const id = ++idRef.current;
      setItems((prev) => [...prev, { id, title, description, variant }]);
      window.setTimeout(() => remove(id), duration);
    },
    [remove],
  );

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* Viewport — top-right, fixed, above everything. */}
      <div className="pointer-events-none fixed right-4 top-4 z-[100] flex w-full max-w-sm flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            className={`sf-toast-in pointer-events-auto flex items-start gap-3 rounded-lg border ${accents[t.variant]} bg-card p-3.5 pr-9 shadow-lg shadow-black/5 backdrop-blur relative`}
            role="status"
          >
            <div className="mt-0.5 shrink-0">{icons[t.variant]}</div>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-medium leading-tight">{t.title}</p>
              {t.description && (
                <p className="mt-0.5 break-words text-xs leading-relaxed text-muted-foreground">
                  {t.description}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => remove(t.id)}
              className="absolute right-2 top-2 rounded p-1 text-muted-foreground/60 transition-colors hover:text-foreground"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastCtx {
  const ctx = React.useContext(ToastContext);
  if (!ctx) {
    // Safe no-op fallback so components rendered outside the provider (e.g. in
    // isolated tests) don't crash — they just silently drop toasts.
    return { toast: () => {} };
  }
  return ctx;
}
