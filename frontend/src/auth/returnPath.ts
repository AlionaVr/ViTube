// The page to go back to after signing in with Google: the trip through Google loses the
// router's state, so it waits in this tab's storage.
const KEY = 'vitube.signInReturnPath'
const LOCAL_PATH = /^\/(?![/\\])/ // "/watch", not "//host" or "/\host"

export function rememberReturnPath(path: string) {
  try {
    sessionStorage.setItem(KEY, path)
  } catch {
    // Storage is off: the user lands on the home page instead.
  }
}

/** The remembered page, once. Only a page of this site; home otherwise. */
export function takeReturnPath(): string {
  let path: string | null = null
  try {
    path = sessionStorage.getItem(KEY)
    sessionStorage.removeItem(KEY)
  } catch {
    // Storage is off: nothing was remembered.
  }
  return path && LOCAL_PATH.test(path) ? path : '/'
}
