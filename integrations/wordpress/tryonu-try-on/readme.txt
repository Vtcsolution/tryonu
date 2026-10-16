=== TryOnU – Virtual Try-On ===
Contributors: tryonu
Tags: woocommerce, virtual try-on, fashion, clothing, ai
Requires at least: 5.8
Tested up to: 6.6
Requires PHP: 7.4
Stable tag: 1.0.0
License: GPLv2 or later

Let shoppers see themselves wearing your products before they buy.

== Description ==

Adds a "Try it on" button to your WooCommerce product pages. A shopper adds a photo of
themselves and, after about 20 to 60 seconds, sees themselves wearing the product.

Each try-on uses 1 credit of your TryOnU account (https://tryonu.app/developers).
A failed try-on gives the credit back.

== Installation ==

1. Plugins → Add New → Upload Plugin, choose tryonu-try-on.zip, Install, Activate.
2. At https://tryonu.app/developers create a Website key for your shop's domain and buy credits.
3. Settings → TryOnU Try-On: paste the key (tou_pk_...) and save.

The button then appears under "Add to cart" on every product with a main image.
To place it yourself, choose "Only where I place [tryonu_button]" and use the shortcode
[tryonu_button] (or [tryonu_button product="123"]).

== Privacy ==

The shopper's photo and the product image are sent to TryOnU (api.tryonu.app) only to make
the try-on picture.
