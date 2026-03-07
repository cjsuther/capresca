import { create } from "zustand";
import { persist } from "zustand/middleware";

export const useAuthStore = create(
  persist(
    (set) => ({
      token: null,
      user: null,
      permissions: null,

      setAuth: (token, user, permissions) => set({ token, user, permissions }),

      logout: () => set({ token: null, user: null, permissions: null }),

      // Helpers
      hasModule: (moduleCode) => {
        const perms = useAuthStore.getState().permissions;
        return perms?.modules?.includes(moduleCode) ?? false;
      },

      hasPermission: (moduleCode, action) => {
        const perms = useAuthStore.getState().permissions;
        return perms?.actions?.[moduleCode]?.includes(action) ?? false;
      },
    }),
    {
      name: "auth-storage",
      // Solo persistir token y datos de sesión (no en localStorage en prod, solo sessionStorage)
      storage: {
        getItem: (name) => {
          const str = sessionStorage.getItem(name);
          return str ? JSON.parse(str) : null;
        },
        setItem: (name, value) => sessionStorage.setItem(name, JSON.stringify(value)),
        removeItem: (name) => sessionStorage.removeItem(name),
      },
    }
  )
);
