import { create } from "zustand"
import { persist } from "zustand/middleware"

export interface AuthUser {
  id: string
  email: string
  full_name?: string
  role?: string
  organization_id?: string
  organization_name?: string
  [key: string]: unknown
}

interface AuthState {
  token: string | null
  user: AuthUser | null
  setSession: (
    token: string,
    user: AuthUser,
  ) => void
  clearSession: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,

      setSession: (token, user) => {
        set({
          token,
          user,
        })
      },

      clearSession: () => {
        set({
          token: null,
          user: null,
        })
      },
    }),
    {
      name: "nooros-auth",
      partialize: (state) => ({
        token: state.token,
        user: state.user,
      }),
    },
  ),
)
