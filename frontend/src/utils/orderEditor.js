export const SHEET_FORMATS = ['A6', 'A5', 'A4', 'A3', 'A3+', 'A3++']

// Match Decimal(str(value)) on the server, while keeping every intermediate
// calculation out of IEEE-754 floating point arithmetic.
const pow10 = (power) => 10n ** BigInt(power)

function decimal(value) {
  const source = String(value ?? 0).trim()
  const match = source.match(/^([+-]?)(\d*)(?:\.(\d*))?(?:e([+-]?\d+))?$/i)
  if (!match || (!match[2] && !match[3])) return { value: 0n, scale: 0 }

  const fraction = match[3] || ''
  const exponent = Number(match[4] || 0)
  const digits = `${match[2] || '0'}${fraction}`.replace(/^0+(?=\d)/, '')
  const sign = match[1] === '-' ? -1n : 1n
  const scale = fraction.length - exponent
  return {
    value: sign * (scale < 0 ? BigInt(digits) * pow10(-scale) : BigInt(digits)),
    scale: Math.max(0, scale),
  }
}

function add(left, right) {
  const scale = Math.max(left.scale, right.scale)
  return {
    value:
      left.value * pow10(scale - left.scale) +
      right.value * pow10(scale - right.scale),
    scale,
  }
}

function multiply(left, right) {
  return { value: left.value * right.value, scale: left.scale + right.scale }
}

function divideBy100(value) {
  return { value: value.value, scale: value.scale + 2 }
}

function roundMoney(value, precision) {
  if (value.scale <= precision)
    return {
      value: value.value * pow10(precision - value.scale),
      scale: precision,
    }

  const divisor = pow10(value.scale - precision)
  const quotient = value.value / divisor
  const remainder = value.value % divisor
  const absoluteRemainder = remainder < 0n ? -remainder : remainder
  return {
    value:
      absoluteRemainder * 2n >= divisor
        ? quotient + (value.value < 0n ? -1n : 1n)
        : quotient,
    scale: precision,
  }
}

const money = (value, precision) => roundMoney(decimal(value), precision)
const sumMoney = (values, precision) =>
  roundMoney(
    values.reduce((sum, value) => add(sum, value), decimal(0)),
    precision,
  )
const toNumber = (value) => Number(value.value) / 10 ** value.scale
const manualOrCalculated = (row, calculated, precision) =>
  row.use_manual_amount ? money(row.manual_amount, precision) : calculated

function validPrecision(value) {
  const precision = Number(value)
  return Number.isInteger(precision) && precision >= 0 && precision <= 9
    ? precision
    : null
}

// Mirrors get_currency_precision() in order_calculations.py. Frappe's
// get_precision() resolves explicit field precision before the system currency
// default; the backend then falls back to the field meta precision, then 2.
export function getOrderCurrencyPrecision(orderTotalField, sysdefaults = {}) {
  const frappePrecision =
    validPrecision(orderTotalField?.precision) ??
    validPrecision(sysdefaults?.currency_precision)
  return frappePrecision ?? validPrecision(orderTotalField?.precision) ?? 2
}

export function calculateOrderPreview(doc, precision = 2) {
  precision = validPrecision(precision) ?? 2
  const itemRows = (doc.order_items || []).map((row) => {
    const customerItem = row.supply_type === 'Customer Item'
    const baseRate = customerItem
      ? money(0, precision)
      : money(row.base_rate, precision)
    const manualRate = money(row.manual_rate, precision)
    const rate = customerItem
      ? money(0, precision)
      : row.use_manual_rate
        ? manualRate
        : baseRate
    const grossAmount = roundMoney(multiply(decimal(row.qty), rate), precision)
    const discount = roundMoney(
      divideBy100(multiply(grossAmount, decimal(row.discount_percentage))),
      precision,
    )
    return {
      amount: roundMoney(
        add(grossAmount, { value: -discount.value, scale: discount.scale }),
        precision,
      ),
      discount,
    }
  })

  const applications = (doc.order_applications || []).map((row) =>
    manualOrCalculated(
      row,
      roundMoney(
        multiply(decimal(row.qty), money(row.rate, precision)),
        precision,
      ),
      precision,
    ),
  )
  const rolls = (doc.dtf_roll_lines || []).map((row) =>
    manualOrCalculated(
      row,
      roundMoney(
        multiply(decimal(row.length_m), money(row.rate_per_meter, precision)),
        precision,
      ),
      precision,
    ),
  )
  const pieces = (doc.dtf_piece_lines || []).map((row) =>
    manualOrCalculated(
      row,
      roundMoney(
        multiply(decimal(row.qty), money(row.unit_price, precision)),
        precision,
      ),
      precision,
    ),
  )
  const itemsSubtotal = sumMoney(
    itemRows.map((row) => row.amount),
    precision,
  )
  const applicationsSubtotal = sumMoney(applications, precision)
  const dtfRollSubtotal = sumMoney(rolls, precision)
  const dtfPieceSubtotal = sumMoney(pieces, precision)
  const discountAmount = sumMoney(
    itemRows.map((row) => row.discount),
    precision,
  )
  const subtotal = sumMoney(
    [itemsSubtotal, applicationsSubtotal, dtfRollSubtotal, dtfPieceSubtotal],
    precision,
  )
  const orderTotal = doc.use_manual_total
    ? money(doc.manual_order_total, precision)
    : subtotal

  return {
    itemsSubtotal: toNumber(itemsSubtotal),
    applicationsSubtotal: toNumber(applicationsSubtotal),
    dtfRollSubtotal: toNumber(dtfRollSubtotal),
    dtfPieceSubtotal: toNumber(dtfPieceSubtotal),
    discountAmount: toNumber(discountAmount),
    subtotal: toNumber(subtotal),
    orderTotal: toNumber(orderTotal),
  }
}

export function synchronizeOrderSummary(doc, precision = 2) {
  const preview = calculateOrderPreview(doc, precision)
  const hasPaymentHistory = Array.isArray(doc.payments)
  const paid = hasPaymentHistory
    ? toNumber(
        sumMoney(
          doc.payments.map((payment) => money(payment.amount, precision)),
          precision,
        ),
      )
    : toNumber(money(doc.paid_amount, precision))

  doc.order_total = preview.orderTotal
  doc.deal_value = preview.orderTotal
  doc.paid_amount = paid
  doc.balance_amount = Math.max(preview.orderTotal - paid, 0)

  if (!['Cancelled', 'Refunded'].includes(doc.payment_status)) {
    if (preview.orderTotal > 0 && paid >= preview.orderTotal) {
      doc.payment_status = 'Paid'
    } else if (paid > 0) {
      doc.payment_status = 'Partially Paid'
    } else if (doc.payment_terms === 'Postpayment' && preview.orderTotal > 0) {
      doc.payment_status = 'Postpaid'
    } else {
      doc.payment_status = 'Unpaid'
    }
  }

  return { ...preview, paidAmount: paid, balanceAmount: doc.balance_amount }
}

export async function selectStudioProduct(row, product, getProduct) {
  row.product = product
  row.base_rate = null
  if (!product) return { error: null }

  try {
    const selectedProduct = await getProduct(product)
    if (row.product !== product) return { error: null }
    row.item_name =
      selectedProduct?.product_name || selectedProduct?.name || product
    if (
      selectedProduct?.standard_rate == null ||
      selectedProduct.standard_rate === ''
    ) {
      return { error: 'missing-standard-rate' }
    }
    row.base_rate = selectedProduct.standard_rate
    return { error: null }
  } catch {
    return { error: 'load-failed' }
  }
}

export function canRemoveOrderItem(doc, itemKey) {
  return !(doc.order_applications || []).some((row) => row.item_key === itemKey)
}

export function incompatibleOrderCategories(doc) {
  const present = {
    products:
      (doc.order_items?.length || 0) + (doc.order_applications?.length || 0) >
      0,
    rolls: (doc.dtf_roll_lines?.length || 0) > 0,
    pieces: (doc.dtf_piece_lines?.length || 0) > 0,
  }
  if (doc.order_type === 'Product Printing')
    return [present.rolls && 'DTF Roll', present.pieces && 'DTF Pieces'].filter(
      Boolean,
    )
  if (doc.order_type === 'DTF Roll')
    return [
      present.products && 'Product Printing',
      present.pieces && 'DTF Pieces',
    ].filter(Boolean)
  if (doc.order_type === 'DTF Pieces')
    return [
      present.products && 'Product Printing',
      present.rolls && 'DTF Roll',
    ].filter(Boolean)
  return []
}
