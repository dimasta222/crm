import { createDocumentResource } from 'frappe-ui'
import { nextTick, ref, shallowRef, watch } from 'vue'

export function useKanbanStatusChange({
  doctype,
  getStatus,
  updateKanbanSettings,
}) {
  const showLostReasonModal = ref(false)
  const lostReasonDocument = shallowRef(null)

  const pendingMoves = new Map()
  const lostReasonQueue = []
  let activeMove = null

  function restoreStatus(flow) {
    if (flow.document?.doc && flow.document.originalDoc) {
      flow.document.doc.status = flow.document.originalDoc.status
    }
  }

  function showNextLostReasonModal() {
    if (activeMove || !lostReasonQueue.length) return

    const flow = lostReasonQueue.shift()
    activeMove = flow

    flow.document.get.fetch().then(
      () => {
        if (activeMove !== flow || flow.settled) return

        flow.document.doc.status = flow.data.to

        const submit = flow.document.save.submit.bind(flow.document.save)
        flow.document.save.submit = (...args) => {
          flow.saving = true
          let request

          try {
            request = submit(...args)
            flow.markServerRequestStarted(true)
          } catch (error) {
            finishPendingMove(flow, false)
            throw error
          }

          Promise.resolve(request).then(
            () => finishPendingMove(flow, true),
            () => finishPendingMove(flow, false),
          )

          return request
        }

        lostReasonDocument.value = flow.document
        showLostReasonModal.value = true
      },
      () => finishPendingMove(flow, false),
    )
  }

  function finishPendingMove(flow, result) {
    if (flow.settled) return

    flow.settled = true
    flow.markServerRequestStarted(false)
    if (!result) restoreStatus(flow)

    if (pendingMoves.get(flow.item) === flow) {
      pendingMoves.delete(flow.item)
    }

    if (activeMove === flow) {
      activeMove = null
      lostReasonDocument.value = null
      showLostReasonModal.value = false
    } else {
      const index = lostReasonQueue.indexOf(flow)
      if (index !== -1) lostReasonQueue.splice(index, 1)
    }

    flow.resolve(result)
    nextTick(showNextLostReasonModal)
  }

  watch(showLostReasonModal, (show) => {
    if (!show && activeMove && !activeMove.saving) {
      finishPendingMove(activeMove, false)
    }
  })

  function requestLostReason(data) {
    const document = createDocumentResource({
      doctype,
      name: data.item,
      auto: false,
    })

    let serverRequestStateSettled = false
    let settleServerRequestStarted
    const serverRequestStarted = new Promise((resolve) => {
      settleServerRequestStarted = resolve
    })

    let flow
    const move = new Promise((resolve) => {
      flow = {
        data,
        item: data.item,
        document,
        resolve,
        saving: false,
        settled: false,
        markServerRequestStarted(started) {
          if (serverRequestStateSettled) return
          serverRequestStateSettled = true
          settleServerRequestStarted(started)
        },
      }

      pendingMoves.set(data.item, flow)
      lostReasonQueue.push(flow)
      showNextLostReasonModal()
    })

    move.serverRequestStarted = serverRequestStarted
    return move
  }

  function beforeStatusChange(data) {
    if (pendingMoves.has(data.item)) return false

    if (data.fieldname !== 'status' || getStatus(data.to)?.type !== 'Lost') {
      return updateKanbanSettings(data)
    }

    return requestLostReason(data)
  }

  return {
    showLostReasonModal,
    lostReasonDocument,
    beforeStatusChange,
  }
}
