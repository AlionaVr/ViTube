import type { User } from '../api/client'

/** Moderators and admins (roles are nested, ADR 0009). The API checks again on every call. */
export function canModerate(user: User): boolean {
  return user.role === 'moderator' || user.role === 'admin'
}

/** Admins ban, terminate and reinstate accounts and read the audit log (ADR 0009). */
export function isAdmin(user: User): boolean {
  return user.role === 'admin'
}
