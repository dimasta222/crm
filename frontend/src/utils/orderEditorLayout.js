const legacyOrderFields = new Set([
  'products',
  'applications',
  'total',
  'net_total',
])

function fieldname(field) {
  return typeof field === 'string' ? field : field?.fieldname
}

export function withoutLegacyOrderFields(tabs) {
  if (!Array.isArray(tabs)) return tabs

  return tabs.map((tab) => ({
    ...tab,
    sections: (tab.sections || [])
      .map((section) => ({
        ...section,
        columns: (section.columns || []).map((column) => ({
          ...column,
          fields: (column.fields || []).filter(
            (field) => !legacyOrderFields.has(fieldname(field)),
          ),
        })),
      }))
      .filter((section) =>
        section.columns.some((column) => column.fields.length),
      ),
  }))
}
