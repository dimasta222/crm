const STORAGE_KEYS = {
  Leads: 'crm:last-view:leads',
  Deals: 'crm:last-view:deals',
}

const REMEMBERED_VIEW_TYPES = new Set(['list', 'kanban'])

export function getRememberedViewType(routeName, storage = localStorage) {
  const key = STORAGE_KEYS[routeName]
  if (!key) return null

  const viewType = storage.getItem(key)
  return REMEMBERED_VIEW_TYPES.has(viewType) ? viewType : null
}

export function rememberViewType(routeName, viewType, storage = localStorage) {
  const key = STORAGE_KEYS[routeName]
  if (!key || !REMEMBERED_VIEW_TYPES.has(viewType)) return

  storage.setItem(key, viewType)
}
