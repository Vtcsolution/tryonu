<?php
/**
 * Plugin Name:       TryOnU – Virtual Try-On
 * Plugin URI:        https://tryonu.app/developers
 * Description:       Adds a "Try it on" button to your WooCommerce product pages: shoppers add a photo and see themselves wearing the product.
 * Version:           1.0.0
 * Requires at least: 5.8
 * Requires PHP:      7.4
 * Author:            TryOnU
 * Author URI:        https://tryonu.app
 * License:           GPLv2 or later
 * Text Domain:       tryonu-try-on
 */

if (!defined('ABSPATH')) {
    exit;
}

define('TRYONU_WIDGET_URL', 'https://tryonu.app/widget.js');
define('TRYONU_OPTION', 'tryonu_settings');

function tryonu_settings() {
    $defaults = [
        'key'         => '',
        'button_text' => 'Try it on',
        'color'       => '#5f7a5b',
        'placement'   => 'after_cart',
    ];
    $saved = get_option(TRYONU_OPTION, []);
    return array_merge($defaults, is_array($saved) ? $saved : []);
}

/* ------------------------------------------------------------------ settings page */

add_action('admin_menu', function () {
    add_options_page('TryOnU Try-On', 'TryOnU Try-On', 'manage_options', 'tryonu-try-on', 'tryonu_settings_page');
});

add_action('admin_init', function () {
    register_setting('tryonu', TRYONU_OPTION, [
        'type'              => 'array',
        'sanitize_callback' => function ($input) {
            $input = is_array($input) ? $input : [];
            $color = sanitize_hex_color($input['color'] ?? '');
            $placement = in_array($input['placement'] ?? '', ['after_cart', 'after_summary', 'shortcode'], true)
                ? $input['placement'] : 'after_cart';
            return [
                'key'         => preg_replace('/[^A-Za-z0-9_\-]/', '', $input['key'] ?? ''),
                'button_text' => sanitize_text_field($input['button_text'] ?? '') ?: 'Try it on',
                'color'       => $color ?: '#5f7a5b',
                'placement'   => $placement,
            ];
        },
    ]);
});

add_filter('plugin_action_links_' . plugin_basename(__FILE__), function ($links) {
    array_unshift($links, '<a href="' . esc_url(admin_url('options-general.php?page=tryonu-try-on')) . '">Settings</a>');
    return $links;
});

function tryonu_settings_page() {
    if (!current_user_can('manage_options')) {
        return;
    }
    $s = tryonu_settings();
    $name = TRYONU_OPTION;
    ?>
    <div class="wrap">
        <h1>TryOnU Try-On</h1>
        <p style="font-size:15px;max-width:640px">
            Shoppers press <b>Try it on</b> on a product page, add a photo of themselves and see themselves wearing the product.
            Each try-on uses 1 credit of your TryOnU account.
        </p>
        <ol style="font-size:14px;max-width:640px">
            <li>Open <a href="https://tryonu.app/developers#keys" target="_blank" rel="noopener">tryonu.app/developers</a> and sign in.</li>
            <li>Create a <b>Website key</b> and enter this site's address: <code><?php echo esc_html(wp_parse_url(home_url(), PHP_URL_HOST)); ?></code></li>
            <li>Paste the key (it starts with <code>tou_pk_</code>) below and save.</li>
        </ol>
        <?php if ($s['key'] && strpos($s['key'], 'tou_sk_') === 0) : ?>
            <div class="notice notice-error"><p>That is a <b>secret</b> key. Never put it in a website: revoke it in the TryOnU portal and create a <b>Website key</b> instead.</p></div>
        <?php endif; ?>
        <form method="post" action="options.php">
            <?php settings_fields('tryonu'); ?>
            <table class="form-table" role="presentation">
                <tr>
                    <th scope="row"><label for="tryonu-key">Website key</label></th>
                    <td><input id="tryonu-key" class="regular-text code" name="<?php echo esc_attr($name); ?>[key]" value="<?php echo esc_attr($s['key']); ?>" placeholder="tou_pk_..." /></td>
                </tr>
                <tr>
                    <th scope="row"><label for="tryonu-text">Button text</label></th>
                    <td><input id="tryonu-text" class="regular-text" name="<?php echo esc_attr($name); ?>[button_text]" value="<?php echo esc_attr($s['button_text']); ?>" /></td>
                </tr>
                <tr>
                    <th scope="row"><label for="tryonu-color">Button colour</label></th>
                    <td><input id="tryonu-color" type="color" name="<?php echo esc_attr($name); ?>[color]" value="<?php echo esc_attr($s['color']); ?>" /></td>
                </tr>
                <tr>
                    <th scope="row">Where the button goes</th>
                    <td>
                        <?php
                        $choices = [
                            'after_cart'    => 'Under the "Add to cart" button (recommended)',
                            'after_summary' => 'Under the product summary',
                            'shortcode'     => 'Only where I place [tryonu_button]',
                        ];
                        foreach ($choices as $value => $label) {
                            printf(
                                '<label style="display:block;margin-bottom:6px"><input type="radio" name="%s[placement]" value="%s" %s /> %s</label>',
                                esc_attr($name),
                                esc_attr($value),
                                checked($s['placement'], $value, false),
                                esc_html($label)
                            );
                        }
                        ?>
                    </td>
                </tr>
            </table>
            <?php submit_button(); ?>
        </form>
    </div>
    <?php
}

/* ------------------------------------------------------------------ the widget script */

add_action('wp_enqueue_scripts', function () {
    $s = tryonu_settings();
    if (!$s['key'] || strpos($s['key'], 'tou_pk_') !== 0) {
        return;
    }
    wp_enqueue_script('tryonu-widget', TRYONU_WIDGET_URL, [], null, true);
});

add_filter('script_loader_tag', function ($tag, $handle) {
    if ($handle !== 'tryonu-widget') {
        return $tag;
    }
    $s = tryonu_settings();
    $attrs = sprintf(
        ' data-key="%s" data-button-text="%s" data-color="%s" defer',
        esc_attr($s['key']),
        esc_attr($s['button_text']),
        esc_attr($s['color'])
    );
    return str_replace(' src=', $attrs . ' src=', $tag);
}, 10, 2);

/* ------------------------------------------------------------------ the button */

function tryonu_button_html($product_id = 0) {
    $s = tryonu_settings();
    if (!$s['key']) {
        return '';
    }
    $product_id = $product_id ?: get_the_ID();
    $image = '';
    $title = '';
    if (function_exists('wc_get_product') && ($product = wc_get_product($product_id))) {
        $image = wp_get_attachment_image_url($product->get_image_id(), 'full');
        $title = $product->get_name();
    }
    if (!$image) {
        $image = get_the_post_thumbnail_url($product_id, 'full');
        $title = $title ?: get_the_title($product_id);
    }
    if (!$image) {
        return '';
    }
    return sprintf(
        '<div class="tryonu-button-wrap"><button type="button" class="tryonu-button" data-tryonu-garment="%s" data-tryonu-name="%s"></button></div>',
        esc_url($image),
        esc_attr($title)
    );
}

add_shortcode('tryonu_button', function ($atts) {
    $atts = shortcode_atts(['product' => 0], $atts, 'tryonu_button');
    return tryonu_button_html(absint($atts['product']));
});

add_action('woocommerce_after_add_to_cart_button', function () {
    if (tryonu_settings()['placement'] === 'after_cart') {
        echo tryonu_button_html(); // phpcs:ignore WordPress.Security.EscapeOutput -- escaped inside
    }
});

add_action('woocommerce_single_product_summary', function () {
    if (tryonu_settings()['placement'] === 'after_summary') {
        echo tryonu_button_html(); // phpcs:ignore WordPress.Security.EscapeOutput -- escaped inside
    }
}, 35);
