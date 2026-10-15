# Fieldwork Supply storefront

This synthetic retail application has no payments, customer accounts or external dependencies.

## Source map

- `index.html` contains the product listing, bag controls and checkout summary.
- `cart.js` owns the in-memory bag state, price calculation, currency formatting and DOM updates.
- `styles.css` defines the responsive storefront and the CSS product illustration.

## Product behavior

The Canvas daypack costs 6,400 cents. Quantity controls accept integers from one through nine. Adding a product increases its quantity; a page reload clears the bag. Decreasing quantity stops at one.

Shipping is 800 cents for nonempty orders below 10,000 cents of merchandise. Orders at or above that merchandise threshold receive complimentary shipping. Empty bags have no shipping charge. Displayed amounts use US dollars and integer cents internally. No tax or coupon feature is implemented.

The bag's line amount, subtotal, shipping and order total are displayed independently. The quantity field and bag count reflect the number of units. Checkout is deliberately disabled because this is a synthetic application.

## Runtime

Serve the directory as static files at `/retail/`. The script is loaded with `defer`; DOM updates happen synchronously on click or quantity-change events. There is no API call, storage persistence, service worker or database in this target application.
