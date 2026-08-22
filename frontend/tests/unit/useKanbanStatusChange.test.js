import { nextTick } from 'vue'
import { useKanbanStatusChange } from '@/composables/useKanbanStatusChange'

const testState = vi.hoisted(() => ({
  document: null,
  documents: new Map(),
}))

vi.mock('frappe-ui', () => ({
  createDocumentResource: vi.fn(
    ({ name }) => testState.documents.get(name) || testState.document,
  ),
}))

describe('Kanban status change flow', () => {
  function createLostDocument(
    name,
    submit = vi.fn().mockResolvedValue({ name }),
  ) {
    return {
      doc: { name, status: 'Open' },
      originalDoc: { name, status: 'Open' },
      get: { fetch: vi.fn().mockResolvedValue() },
      save: { submit },
    }
  }

  function setupLostFlow(
    submit = vi.fn().mockResolvedValue({ name: 'LEAD-1' }),
  ) {
    testState.document = createLostDocument('LEAD-1', submit)
    const updateKanbanSettings = vi.fn()
    const flow = useKanbanStatusChange({
      doctype: 'CRM Lead',
      getStatus: (status) => ({ type: status }),
      updateKanbanSettings,
    })
    const move = flow.beforeStatusChange({
      item: 'LEAD-1',
      from: 'Open',
      to: 'Lost',
      fieldname: 'status',
    })

    return { flow, move, submit, updateKanbanSettings }
  }

  async function waitForLostModal() {
    await Promise.resolve()
    await nextTick()
  }

  beforeEach(() => {
    testState.document = null
    testState.documents.clear()
  })

  it('uses the Lost reason document flow and waits for its save', async () => {
    const { flow, move, submit, updateKanbanSettings } = setupLostFlow()

    let settled = false
    move.then(() => (settled = true))
    await waitForLostModal()

    expect(testState.document.get.fetch).toHaveBeenCalledOnce()
    expect(testState.document.doc.status).toBe('Lost')
    expect(flow.showLostReasonModal.value).toBe(true)
    expect(updateKanbanSettings).not.toHaveBeenCalled()
    expect(settled).toBe(false)

    testState.document.save.submit()
    await expect(move).resolves.toBe(true)
    await expect(move.serverRequestStarted).resolves.toBe(true)

    expect(submit).toHaveBeenCalledOnce()
    expect(settled).toBe(true)
  })

  it('keeps the card in its source status when Lost is cancelled', async () => {
    const { flow, move, submit } = setupLostFlow()
    await waitForLostModal()

    testState.document.doc.status = testState.document.originalDoc.status
    flow.showLostReasonModal.value = false

    await expect(move).resolves.toBe(false)
    await expect(move.serverRequestStarted).resolves.toBe(false)
    expect(testState.document.doc.status).toBe('Open')
    expect(submit).not.toHaveBeenCalled()
  })

  it('does not replace the pending move on a second drag of the same card', async () => {
    const { flow, move, updateKanbanSettings } = setupLostFlow()
    await waitForLostModal()
    const pendingDocument = flow.lostReasonDocument.value

    const secondMove = flow.beforeStatusChange({
      item: 'LEAD-1',
      from: 'Open',
      to: 'Contacted',
      fieldname: 'status',
    })

    expect(secondMove).toBe(false)
    expect(flow.lostReasonDocument.value).toBe(pendingDocument)
    expect(flow.showLostReasonModal.value).toBe(true)
    expect(updateKanbanSettings).not.toHaveBeenCalled()

    updateKanbanSettings.mockResolvedValue('saved')
    await expect(
      flow.beforeStatusChange({
        item: 'LEAD-2',
        from: 'Open',
        to: 'Contacted',
        fieldname: 'status',
      }),
    ).resolves.toBe('saved')

    flow.showLostReasonModal.value = false
    await expect(move).resolves.toBe(false)
  })

  it('cleans the document guard after cancel so the card can move again', async () => {
    const { flow, move, updateKanbanSettings } = setupLostFlow()
    await waitForLostModal()

    flow.showLostReasonModal.value = false
    await expect(move).resolves.toBe(false)

    updateKanbanSettings.mockResolvedValue('saved')
    await expect(
      flow.beforeStatusChange({
        item: 'LEAD-1',
        from: 'Open',
        to: 'Contacted',
        fieldname: 'status',
      }),
    ).resolves.toBe('saved')
  })

  it('keeps the card in its source status when Lost is closed', async () => {
    const { flow, move, submit } = setupLostFlow()
    await waitForLostModal()

    flow.showLostReasonModal.value = false

    await expect(move).resolves.toBe(false)
    await expect(move.serverRequestStarted).resolves.toBe(false)
    expect(testState.document.doc.status).toBe('Open')
    expect(submit).not.toHaveBeenCalled()
  })

  it('finishes the Lost move and restores status when its API save fails', async () => {
    const error = { messages: ['Save failed'] }
    const { flow, move } = setupLostFlow(vi.fn().mockRejectedValue(error))
    await waitForLostModal()

    const request = testState.document.save.submit()

    await expect(request).rejects.toBe(error)
    await expect(move).resolves.toBe(false)
    await expect(move.serverRequestStarted).resolves.toBe(true)
    expect(testState.document.doc.status).toBe('Open')
    expect(flow.lostReasonDocument.value).toBe(null)
    expect(flow.showLostReasonModal.value).toBe(false)
  })

  it('cleans the document guard after a rejected save', async () => {
    const error = { messages: ['Save failed'] }
    const { flow, move, updateKanbanSettings } = setupLostFlow(
      vi.fn().mockRejectedValue(error),
    )
    await waitForLostModal()

    await expect(testState.document.save.submit()).rejects.toBe(error)
    await expect(move).resolves.toBe(false)

    updateKanbanSettings.mockResolvedValue('saved')
    await expect(
      flow.beforeStatusChange({
        item: 'LEAD-1',
        from: 'Open',
        to: 'Contacted',
        fieldname: 'status',
      }),
    ).resolves.toBe('saved')
  })

  it('passes lost_reason and lost_notes through the document save flow', async () => {
    const savedValues = {}
    const submit = vi.fn(() => {
      savedValues.lost_reason = testState.document.doc.lost_reason
      savedValues.lost_notes = testState.document.doc.lost_notes
      return Promise.resolve({ name: 'LEAD-1' })
    })
    const { move } = setupLostFlow(submit)
    await waitForLostModal()

    testState.document.doc.lost_reason = 'Other'
    testState.document.doc.lost_notes = 'Budget was cancelled'
    testState.document.save.submit()

    await expect(move).resolves.toBe(true)
    expect(savedValues).toEqual({
      lost_reason: 'Other',
      lost_notes: 'Budget was cancelled',
    })
  })

  it('keeps raw non-Lost status values in the existing update flow', async () => {
    const updateKanbanSettings = vi.fn().mockResolvedValue('saved')
    const flow = useKanbanStatusChange({
      doctype: 'CRM Deal',
      getStatus: () => ({ type: 'Open' }),
      updateKanbanSettings,
    })
    const data = {
      item: 'DEAL-1',
      from: 'Qualification',
      to: 'Commercial Offer',
      fieldname: 'status',
    }

    await expect(flow.beforeStatusChange(data)).resolves.toBe('saved')
    expect(updateKanbanSettings).toHaveBeenCalledWith(data)
  })

  it('queues two Lost cards when the first is cancelled and the second is submitted', async () => {
    const first = createLostDocument('LEAD-1')
    const second = createLostDocument('LEAD-2')
    testState.documents.set('LEAD-1', first)
    testState.documents.set('LEAD-2', second)
    const flow = useKanbanStatusChange({
      doctype: 'CRM Lead',
      getStatus: (status) => ({ type: status }),
      updateKanbanSettings: vi.fn(),
    })

    const firstMove = flow.beforeStatusChange({
      item: 'LEAD-1',
      from: 'Open',
      to: 'Lost',
      fieldname: 'status',
    })
    const secondMove = flow.beforeStatusChange({
      item: 'LEAD-2',
      from: 'Open',
      to: 'Lost',
      fieldname: 'status',
    })
    await waitForLostModal()

    expect(flow.lostReasonDocument.value).toBe(first)
    flow.showLostReasonModal.value = false
    await expect(firstMove).resolves.toBe(false)
    await waitForLostModal()

    expect(flow.lostReasonDocument.value).toBe(second)
    second.save.submit()
    await expect(secondMove).resolves.toBe(true)
  })

  it('queues two Lost cards when the first is submitted and the second is cancelled', async () => {
    const first = createLostDocument('LEAD-1')
    const second = createLostDocument('LEAD-2')
    testState.documents.set('LEAD-1', first)
    testState.documents.set('LEAD-2', second)
    const flow = useKanbanStatusChange({
      doctype: 'CRM Lead',
      getStatus: (status) => ({ type: status }),
      updateKanbanSettings: vi.fn(),
    })

    const firstMove = flow.beforeStatusChange({
      item: 'LEAD-1',
      from: 'Open',
      to: 'Lost',
      fieldname: 'status',
    })
    const secondMove = flow.beforeStatusChange({
      item: 'LEAD-2',
      from: 'Open',
      to: 'Lost',
      fieldname: 'status',
    })
    await waitForLostModal()

    first.save.submit()
    await expect(firstMove).resolves.toBe(true)
    await waitForLostModal()

    expect(flow.lostReasonDocument.value).toBe(second)
    flow.showLostReasonModal.value = false
    await expect(secondMove).resolves.toBe(false)
  })

  it('allows another card to make a regular move while a Lost modal is open', async () => {
    const { flow, move, updateKanbanSettings } = setupLostFlow()
    updateKanbanSettings.mockResolvedValue('saved')
    await waitForLostModal()

    await expect(
      flow.beforeStatusChange({
        item: 'LEAD-2',
        from: 'Open',
        to: 'Contacted',
        fieldname: 'status',
      }),
    ).resolves.toBe('saved')
    expect(flow.showLostReasonModal.value).toBe(true)

    flow.showLostReasonModal.value = false
    await expect(move).resolves.toBe(false)
  })
})
