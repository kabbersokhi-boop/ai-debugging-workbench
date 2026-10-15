// Cart state and checkout totals for the Fieldwork Supply storefront.
const UNIT_PRICE_CENTS = 6400;
const SHIPPING_CENTS = 800;
const FREE_SHIPPING_THRESHOLD_CENTS = 10000;
let quantity = 0;

function calculateTotals(items) {
  const subtotal = items.reduce((sum, item) => sum + item.unitPriceCents * item.quantity, 0);
  const shipping =
    subtotal === 0 || subtotal >= FREE_SHIPPING_THRESHOLD_CENTS
      ? 0
      : SHIPPING_CENTS;
  return { subtotal, shipping, total: subtotal - shipping };
}

function money(cents) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

function setMoney(testId, cents) {
  const element = document.querySelector(`[data-testid="${testId}"]`);
  element.textContent = money(cents);
  element.dataset.cents = String(cents);
}

function render() {
  document.querySelector("#empty").hidden = quantity > 0;
  document.querySelector("#cart-item").hidden = quantity === 0;
  document.querySelector("#quantity").value = quantity || 1;
  document.querySelector('[data-testid="bag-count"]').textContent = quantity;
  document.querySelector('[data-testid="item-count"]').textContent =
    `${quantity} ${quantity === 1 ? "item" : "items"}`;
  document.querySelector("#decrease").disabled = quantity <= 1;
  document.querySelector("#increase").disabled = quantity >= 9;
  const items = quantity
    ? [{ unitPriceCents: UNIT_PRICE_CENTS, quantity }]
    : [];
  const totals = calculateTotals(items);
  setMoney("line-total", quantity * UNIT_PRICE_CENTS);
  setMoney("subtotal", totals.subtotal);
  setMoney("shipping", totals.shipping);
  setMoney("total", totals.total);
}

document.querySelector("#add-to-cart").addEventListener("click", () => {
  quantity = Math.min(9, quantity + 1);
  render();
});
document.querySelector("#increase").addEventListener("click", () => {
  quantity = Math.min(9, quantity + 1);
  render();
});
document.querySelector("#decrease").addEventListener("click", () => {
  quantity = Math.max(1, quantity - 1);
  render();
});
document.querySelector("#quantity").addEventListener("change", (event) => {
  const value = Number.parseInt(event.target.value, 10);
  quantity = Number.isFinite(value) ? Math.max(1, Math.min(9, value)) : 1;
  render();
});
render();
