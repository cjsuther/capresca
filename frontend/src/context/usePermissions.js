import { useAuthStore } from "./authStore";

export function useHasModule(moduleCode) {
  return useAuthStore((s) => s.permissions?.modules?.includes(moduleCode) ?? false);
}

export function useHasPermission(moduleCode, action) {
  return useAuthStore((s) => s.permissions?.actions?.[moduleCode]?.includes(action) ?? false);
}

export function useUser() {
  return useAuthStore((s) => s.user);
}

export function useIsAuthenticated() {
  return useAuthStore((s) => !!s.token);
}
