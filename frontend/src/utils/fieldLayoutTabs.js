export function shouldUseDetailsTabFallback(doctype, tabs, index) {
  return (
    doctype === 'CRM Deal' && tabs.length > 1 && index === 0 && !tabs[0]?.label
  )
}
