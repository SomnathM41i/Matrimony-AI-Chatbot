let _navigate = null

export function setNavigate(fn) {
  _navigate = fn
}

export function navigateTo(path) {
  if (_navigate) {
    _navigate(path)
  }
}
