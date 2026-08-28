export type ApiErrorPayload =
  | Record<string, unknown>
  | unknown[]
  | string
  | null

export type CurrentUser = {
  id: string
  email: string
}

export type CsrfResponse = {
  csrfToken: string
}
