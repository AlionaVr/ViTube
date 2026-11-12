/** The users.handle rule (HANDLE_PATTERN in the API): a malformed handle needs no request. */
export const HANDLE = /^[A-Za-z0-9._-]{3,30}$/
